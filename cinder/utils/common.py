import dataclasses
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from io import BytesIO

import httpx
import requests
from appdirs import AppDirs
from python_on_whales import docker

app_dir = AppDirs("Cinder", "Cinder")


def load_settings():
    settings = {
        "central_rest_api": {
            "host": "localhost",
            "port": 8000,
            "protocol": "http",
            "api_key": ""},
        "project_folders": ["unprocessed", "searched", "differential_analysis", "sample_annotation", "other_files",
                        "comparison_matrix"]
    }
    if os.path.exists(os.path.join(app_dir.user_config_dir, "data_manager_config.json")):
        with open(os.path.join(app_dir.user_config_dir, "data_manager_config.json"), "r") as f:
            settings = json.load(f)

    else:
        with open(os.path.join(app_dir.user_config_dir, "data_manager_config.json"), "w") as f:
            json.dump(settings, f)
    return settings


def load_local_db():
    return ProjectDatabase(os.path.join(app_dir.user_config_dir, "data_manager.db"))


@dataclass
class ProjectFile:
    filename: str
    path: tuple[str, ...]
    sha1: str
    remote_id: int = None

    def to_dict(self):
        d = dataclasses.asdict(self)
        del d["remote_id"]
        return d


@dataclass
class Project:
    project_id: int
    description: str
    project_global_id: str
    project_name: str
    project_path: str
    project_data_path: str
    project_metadata: dict
    project_files: dict[str, list[ProjectFile]]
    remote_id: int = None
    project_hash: str = None

    def to_dict(self):
        d = dataclasses.asdict(self)
        del d["remote_id"]
        return d

    def calculate_sha1_hash_of_file(self, file: str) -> str:
        """Calculate sha1 hash of a file"""

        sha1_hash = hashlib.sha1()
        with open(file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()

    def refresh(self):
        """Walk through the project data subfolders and update the file lists for unprocessed, differential analysis, sample annotation, other files, and comparison matrix"""
        sha1_list = []
        temp = {
            i: [] for i in self.project_files
        }
        settings = load_settings()
        for root, dirs, files in os.walk(self.project_data_path):
            item_data_path = root.replace(self.project_data_path, "").lstrip(os.sep)
            for cat in temp:
                if item_data_path.startswith(cat):
                    for file in files:
                        data = ProjectFile(
                            filename=file,
                            path=tuple(item_data_path.split(os.sep)),
                            sha1=self.calculate_sha1_hash_of_file(
                                os.path.join(self.project_data_path, root, file))
                        )
                        for j in self.project_files[cat]:
                            if data.sha1 == j.sha1 and data.filename == j.filename and data.path == j.path:
                                data.remote_id = j.remote_id
                        sha1_list.append(data.sha1)
                        temp[cat].append(data)
                        print(files)

        # check and remove from array if file is not in project folder
        removed_file = []
        for cat in temp:
            for i in self.project_files[cat]:
                if i not in temp[cat]:
                    removed_file.append(i)
            if cat not in self.project_files:
                os.makedirs(os.path.join(self.project_data_path, cat), exist_ok=True)
            self.project_files[cat] = temp[cat]
        s1 = hashlib.sha1()
        for s in sha1_list:
            s1.update(s.encode('utf-8'))
        self.project_hash = s1.hexdigest()
        with open(os.path.join(self.project_path, "project.sha1"), "w") as f:
            f.write(self.project_hash)

        with open(os.path.join(self.project_path, "project.json"), "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        self.project_json_hash = self.calculate_sha1_hash_of_file(os.path.join(self.project_path, "project.json"))
        return removed_file


    def get_project_hash(self):
        """Get project hash"""
        with open(os.path.join(self.project_path, "project.sha1"), "rt") as f:
            return f.read()

    @staticmethod
    def perform_differential_analysis(self, data_path: str, unprocessed_file: str, annotation_file: str,
                                      comparison_matrix_file: str, output_differential_analysis_file: str,
                                      index_cols: str, column_na_filter_threshold: float = 0.7,
                                      row_na_filter_threshold: float = 0.7, imputation_method: str = "knn",
                                      normalization_method: str = "quantiles.robust",
                                      aggregation_method: str = "MsCoreUtils::robustSummary",
                                      aggregation_column: str = "", docker_image="noatgnu/coral:0.0.1"):
        """Perform differential analysis on the unprocessed files using annotation files and comparison matrix files with docker image noatgnu/coral:0.0.1"""
        unprocessed_file = os.path.join("/data", "unprocessed", unprocessed_file)
        annotation_file = os.path.join("/data", "sample_annotation", annotation_file)
        comparison_matrix_file = os.path.join("/data", "comparison_matrix", comparison_matrix_file)
        output_differential_analysis_file = os.path.join("/data", "differential_analysis",
                                                         output_differential_analysis_file)
        command = ["-u", unprocessed_file, "-a", annotation_file, "-c", comparison_matrix_file, "-o",
                   output_differential_analysis_file, "-x", index_cols, "-f", column_na_filter_threshold, "-r",
                   row_na_filter_threshold, "-i", imputation_method, "-n", normalization_method]
        if aggregation_column != "":
            command += ["-g", aggregation_method, "-t", aggregation_column]
        docker.run(image=docker_image, volumes=[(data_path, "/data")], command=command, remove=True, tty=True,
                   interactive=False)
        with open(os.path.join(self.project_data_path, "differential_analysis",
                               f"{output_differential_analysis_file}.json"), "w") as f:
            json.dump(command, f, indent=2)

    def remove_file(self, file: ProjectFile):
        """Remove file from project"""
        os.remove(os.path.join(self.project_data_path, *file.path, file.filename))

    def remove_project(self, db):
        """Remove project from database and delete project folder"""
        if self.project_id:
            db.delete_project(self.project_id)
        shutil.rmtree(self.project_path)


@dataclass
class QueryResult:
    total: int
    offset: int
    limit: int
    data: list[Project]


class ProjectDatabase:
    def __init__(self, path=":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, location TEXT, global_id TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, sha1_hash TEXT, remote_id INTEGER)")

    def create_project(self, name: str, description: str, location: str, hash: str) -> dict:
        """Create project and return project id"""
        uu = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO projects (name, description, location, global_id, sha1_hash) VALUES (?, ?, ?, ?, ?)",
            (name, description, location, uu, hash))
        self.conn.commit()
        id = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": id, "global_id": uu}

    def update_project(self, project_id: int, name: str, description: str, location: str, hash: str):
        """Update project name and description"""
        self.conn.execute("UPDATE projects SET name=?, description=?, location=?, sha1_hash=? WHERE id=?",
                          (name, description, project_id, location, hash))
        self.conn.commit()

    def delete_project(self, project_id: int):
        """Delete project"""
        self.conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        self.conn.commit()

    def get_project(self, project_id: int) -> Project:
        """Get project by id and load as a Project object"""
        data = self.conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if data:
            project_dir = data[3]
            project = load_project(project_dir)
            return project
        else:
            raise ValueError(f"Project with id {project_id} not found")

    def search_projects(self, term: str = "", offset: int = 0, limit: int = 20) -> QueryResult:
        """Search for projects by name or description with offset and limit of how many entries to return, also return total number of entries"""
        data = self.conn.execute("SELECT * FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT ? OFFSET ?",
                                 (f"%{term}%", f"%{term}%", limit, offset)).fetchall()
        projects = []
        for d in data:
            project_dir = d[3]
            project = load_project(project_dir)
            projects.append(project)
        total = self.conn.execute("SELECT COUNT(*) FROM projects WHERE name LIKE ? OR description LIKE ?",
                                  (f"%{term}%", f"%{term}%")).fetchone()[0]
        return QueryResult(total=total, offset=offset, limit=limit, data=projects)

    def recreate_database(self):
        """Recreate database"""
        self.conn.execute("DROP TABLE IF EXISTS projects")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, location TEXT, global_id TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, sha1_hash TEXT)")
        self.conn.commit()

    def update_remote_id(self, remote_id: int, project_id: int):
        """Update remote id"""
        self.conn.execute("UPDATE projects SET remote_id=? WHERE id=?", (remote_id, project_id))
        self.conn.commit()


def load_project(project_folder: str) -> Project:
    """Load project from project folder"""
    with open(os.path.join(project_folder, "project.json"), "r") as f:
        project_dict = json.load(f)
        project = Project(**project_dict)
    return project


class CorpusServer:
    def __init__(self, host: str, api_key: str, local_db: ProjectDatabase = None):
        self.host = host
        self.api_key = api_key
        self.post_project_path = f"{host}/api/projects"
        self.db = local_db
        self.settings = load_settings()

    async def create_project(self, project: Project):
        """Create project on server"""
        payload = {
            "name": project.project_name,
            "description": project.description,
            "hash": open(os.path.join(project.project_path, "project.sha1"), "rt").read(),
            "metadata": project.to_dict(),
            "global_id": project.project_global_id
        }
        async with httpx.AsyncClient(
                headers={"X-API-Key": f"{self.api_key}", "content-type": "application/json"}) as client:
            d = await client.post(self.post_project_path, json=payload)
            project.remote_id = d.json()["id"]
            project.refresh()
            self.db.update_remote_id(project_id=project.project_id, remote_id=project.remote_id)
            return project

    async def update_project(self, project: Project):
        """Update project on server"""
        async with httpx.AsyncClient(
                headers={"X-API-Key": f"{self.api_key}", "content-type": "application/json"}) as client:
            d = await client.patch(f"{self.post_project_path}/{project.remote_id}", json={
                "name": project.project_name,
                "description": project.description,
                "hash": open(os.path.join(project.project_path, "project.sha1"), "rt").read(),
                "metadata": json.dumps(project.to_dict()),
                "global_id": project.project_global_id}
                                   )

    async def get_project(self, project_id: int):
        """Get project from server"""
        async with httpx.AsyncClient(headers={"X-API-Key": f"{self.api_key}"}) as client:
            d = await client.get(f"{self.post_project_path}/{project_id}")
            d = d.json()
            print(d)
            project = Project(
                project_id=d["metadata"]["project_id"],
                project_path=d["metadata"]["project_path"],
                project_data_path=d["metadata"]["project_data_path"],
                project_metadata={},
                project_name=d["name"],
                description=d["description"],
                project_global_id=d["global_id"],
                project_files=d["metadata"]["project_files"],
                remote_id=d["id"],
                project_hash=d["hash"]
            )
            return project

    async def get_project_files(self, project_id: int):
        """Get project files from server"""
        async with httpx.AsyncClient(headers={"X-API-Key": f"{self.api_key}"}) as client:
            d = await client.get(f"{self.post_project_path}/{project_id}/files")
            return d

    async def remove_file(self, file: ProjectFile):
        """Remove file from server"""
        async with httpx.AsyncClient(headers={"X-API-Key": f"{self.api_key}"}) as client:
            d = await client.delete(f"{self.host}/api/files/{file.remote_id}")
            if d.status_code == 204:
                return True
            else:
                return False

    async def remove_remote_file_not_in_local_project(self, project: Project):
        """Check if file exists in project"""
        files = await self.get_project_files(project.remote_id)
        files = files.json()
        result = {}
        for f in files:
            path = tuple()
            if f["path"]:
                path = tuple(f["path"])
            cat = f["file_category"]
            p_f = ProjectFile(filename=f["filename"], sha1=f["hash"], remote_id=f["id"], path=path)
            if p_f not in project.project_files[cat]:
                await self.remove_file(p_f)
            else:
                if cat not in result:
                    result[cat] = []
                result[cat].append(f)
        return result

    async def upload_file(self, project: Project):
        """Get remote file lists. Check if file exists on server using ProjectFile.remote_id, if not, upload file, if they are, check if hash matches, if not, upload file"""
        result = await self.remove_remote_file_not_in_local_project(project)
        filename_map = {}

        for cat in self.settings["project_folders"]:
            for i, file in enumerate(project.project_files[cat]):
                if not file.remote_id:
                    file = await self.upload_chunk(file, project, cat)
                    project.project_files[cat][i].remote_id = file.remote_id
                    yield file

    async def upload_chunk(self, file: ProjectFile, project: Project, category: str, offset: int = 0):
        """Upload file in chunks"""
        async with httpx.AsyncClient(headers={"X-API-Key": f"{self.api_key}"}) as client:
            d = await client.post(f"{self.host}/api/files/chunked",
                                  json={
                                      "filename": file.filename,
                                      "size": os.path.getsize(
                                          os.path.join(project.project_data_path, *file.path, file.filename)),
                                      "data_hash": file.sha1,
                                      "file_category": category
                                  })
            upload_id = d.json()["upload_id"]
            with open(os.path.join(project.project_data_path, *file.path, file.filename),
                      "rb") as f:
                # read the file in chunk of d.chunk_size and upload it
                while True:
                    chunk = f.read(d.json()["chunk_size"])
                    if not chunk:
                        break
                    chunk_file = BytesIO(chunk)
                    progress = await client.post(f"{self.host}/api/files/chunked/{upload_id}",
                                                 data={"offset": offset}, files={"chunk": chunk_file})
                    if progress.json()["status"] == "complete":
                        break
                    else:
                        offset = progress.json()["offset"]
                if file.remote_id:
                    if category in ["unprocessed", "differential_analysis"] and (
                            file.filename.endswith(".tsv") or file.filename.endswith(".txt") or file.filename.endswith(
                            ".csv")):
                        file = await client.post(f"{self.host}/api/files/chunked/{upload_id}/complete",
                                                 json={"load_file_content": True, "file_id": file.remote_id})
                    else:
                        file = await client.post(f"{self.host}/api/files/chunked/{upload_id}/complete",
                                                 json={"file_id": file.remote_id})
                else:
                    if category in ["unprocessed", "differential_analysis"] and (
                            file.filename.endswith(".tsv") or file.filename.endswith(".txt") or file.filename.endswith(
                            ".csv")):
                        result = await client.post(f"{self.host}/api/files/chunked/{upload_id}/complete",
                                                   json={"create_file": True, "load_file_content": True, "project_id": project.remote_id, "path": file.path})
                    else:
                        result = await client.post(f"{self.host}/api/files/chunked/{upload_id}/complete",
                                                   json={"create_file": True, "project_id": project.remote_id, "path": file.path})
                    file.remote_id = result.json()["id"]
            return file

    async def download_file(self, file: ProjectFile, project: Project):
        """Download file from server"""
        async with httpx.AsyncClient(headers={"X-API-Key": f"{self.api_key}", "accept": "*/*"}, follow_redirects=True) as client:
            async with client.stream('GET', f'{self.host}/api/files/{file.remote_id}/download') as r:
                with open(os.path.join(project.project_data_path, *file.path, file.filename), "wb") as f:
                    async for chunk in r.aiter_bytes():
                        f.write(chunk)
            #r = await client.get(f'{self.host}/api/files/{file.remote_id}/download')
            #with open(os.path.join(project.project_data_path, *file.path, file.filename), "wb") as f:
            #    f.write(r.content)
            #r = requests.get(f'{self.host}/api/files/{file.remote_id}/download', headers={"X-API-Key": f"{self.api_key}"}, allow_redirects=True)
            #with open(os.path.join(project.project_data_path, *file.path, file.filename), "wb") as f:
            #    print(r.status_code)
            #    f.write(r.content)
