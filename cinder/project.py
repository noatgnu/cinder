import dataclasses
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass

from python_on_whales import docker


@dataclass
class Project:
    project_id: int
    description: str
    project_global_id: str
    project_name: str
    project_path: str
    project_data_path: str
    project_metadata: dict
    unprocessed: list[str]
    differential_analysis: list[str]
    sample_annotation: list[str]
    other_files: list[str]
    comparison_matrix: list[str]

    def calculate_md5_hash_of_file(self, file: str) -> str:
        """Calculate md5 hash of a file"""
        import hashlib
        md5_hash = hashlib.md5()
        with open(file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def refresh(self):
        """Walk through the project data subfolders and update the file lists for unprocessed, differential analysis, sample annotation, other files, and comparison matrix"""
        self.unprocessed = []
        self.differential_analysis = []
        self.sample_annotation = []
        self.other_files = []
        self.comparison_matrix = []
        for root, dirs, files in os.walk(self.project_data_path):
            if "unprocessed" in root:
                for file in files:
                    if not file.endswith(".json"):
                        self.unprocessed.append(file)
                        with open(os.path.join(self.project_data_path, "unprocessed", f"{file}.md5"), "w") as f:
                            f.write(self.calculate_md5_hash_of_file(os.path.join(self.project_data_path, "unprocessed", file)))
            elif "differential_analysis" in root:
                for file in files:
                    if not file.endswith(".json"):
                        self.differential_analysis.append(file)
                        with open(os.path.join(self.project_data_path, "differential_analysis", f"{file}.md5"), "w") as f:
                            f.write(self.calculate_md5_hash_of_file(os.path.join(self.project_data_path, "differential_analysis", file)))
            elif "sample_annotation" in root:
                for file in files:
                    if not file.endswith(".json"):
                        self.sample_annotation.append(file)
                        with open(os.path.join(self.project_data_path, "sample_annotation", f"{file}.md5"), "w") as f:
                            f.write(self.calculate_md5_hash_of_file(os.path.join(self.project_data_path, "sample_annotation", file)))
            elif "comparison_matrix" in root:
                for file in files:
                    if not file.endswith(".json"):
                        self.comparison_matrix.append(file)
                        with open(os.path.join(self.project_data_path, "comparison_matrix", f"{file}.md5"), "w") as f:
                            f.write(self.calculate_md5_hash_of_file(os.path.join(self.project_data_path, "comparison_matrix", file)))
            elif "other_files" in root:
                for file in files:
                    if not file.endswith(".json"):
                        self.other_files.append(file)
                        with open(os.path.join(self.project_data_path, "other_files", f"{file}.md5"), "w") as f:
                            f.write(self.calculate_md5_hash_of_file(os.path.join(self.project_data_path, "other_files", file)))
        with open(os.path.join(self.project_path, "project.json"), "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)

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
            "CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, location TEXT, global_id TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")

    def create_project(self, name: str, description: str, location: str) -> dict:
        """Create project and return project id"""
        uu = str(uuid.uuid4())
        self.conn.execute("INSERT INTO projects (name, description, location, global_id) VALUES (?, ?, ?, ?)",
                          (name, description, location, uu))
        self.conn.commit()
        id = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": id, "global_id": uu}


    def update_project(self, project_id: int, name: str, description: str):
        """Update project name and description"""
        self.conn.execute("UPDATE projects SET name=?, description=? WHERE id=?", (name, description, project_id))
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



def load_project(project_folder: str) -> Project:
    """Load project from project folder"""
    with open(os.path.join(project_folder, "project.json"), "r") as f:
        project_dict = json.load(f)
        project = Project(**project_dict)
    return project



