import json
import os

from click import command, option

from cinder.utils.common import load_local_db, load_settings, ProjectFile, CorpusServer
import asyncio

db = load_local_db()
settings = load_settings()


@command()
@option("-p", "--project-id", type=int, help="Remote Project ID", required=True)
@option("-h", "--hostname", type=str, help="Remote Server Hostname", required=False)
@option("-p", "--port", type=int, help="Remote Server Port", required=False)
@option("-pr", "--protocol", type=str, help="Remote Server Protocol", required=False)
@option("-a", "--api-key", type=str, help="Authentication API Key", required=False)
@option("-o", "--output-path", type=str, help="Project Location Path", required=False)
def main(project_id, hostname, port, protocol, api_key, output_path):
    if api_key:
        settings["central_rest_api"]["api_key"] = api_key
    if hostname:
        settings["central_rest_api"]["host"] = hostname
    if port:
        settings["central_rest_api"]["port"] = port
    if protocol:
        settings["central_rest_api"]["protocol"] = protocol

    base_url = f"{settings['central_rest_api']['protocol']}://{settings['central_rest_api']['host']}:{settings['central_rest_api']['port']}"

    corpus = CorpusServer(base_url, api_key, db)
    project = asyncio.run(corpus.get_project(project_id))
    if output_path:
        project.project_path = output_path
    else:

        project.project_path = os.path.join(os.getcwd(), project.project_name)

    os.makedirs(project.project_name, exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data"), exist_ok=True)

    project.project_data_path = os.path.join(project.project_path, "data")
    os.makedirs(os.path.join(project.project_name, "data", "unprocessed"), exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data", "differential_analysis"), exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data", "sample_annotation"), exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data", "other_files"), exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data", "comparison_matrix"), exist_ok=True)
    for i in ["unprocessed", "differential_analysis", "sample_annotation", "other_files", "comparison_matrix"]:
        file_list = getattr(project, i)
        for n, file in enumerate(file_list):
            file = ProjectFile(**file)
            asyncio.run(corpus.download_file(file, project))
    with open(os.path.join(project.project_path, "project.json"), "w") as f:
        json.dump(project.to_dict(), f, indent=2)
    project.refresh()
    created = db.create_project(project.project_name, project.description, project.project_path,
                                project.get_project_hash())
    db.update_remote_id(project_id, created["id"])
    project.id = created["id"]
    project.project_global_id = created["global_id"]
    project.refresh()
