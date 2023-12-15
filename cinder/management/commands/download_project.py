import json
import os

import click

from cinder.utils.common import load_local_db, load_settings, ProjectFile, CorpusServer
import asyncio
import requests
db = load_local_db()
settings = load_settings()
@click.command()
@click.option("-p", "--project-id", type=int, help="Remote Project ID", required=True)
@click.option("--hostname", type=str, help="Remote Server Hostname", required=False)
@click.option("--port", type=int, help="Remote Server Port", required=False)
@click.option("--protocol", type=str, help="Remote Server Protocol", required=False)
@click.option("-a", "--api-key", type=str, help="Authentication API Key", required=False)
@click.option("-o", "--output-path", type=str, help="Project Location Path", required=False)
def main(project_id, hostname, port, protocol, api_key, output_path):
    print(settings)
    print(project_id, hostname, port, protocol, api_key, output_path)
    if api_key:
        settings["central_rest_api"]["api_key"] = api_key
    if hostname:
        settings["central_rest_api"]["host"] = hostname
    if port:
        settings["central_rest_api"]["port"] = port
    if protocol:
        settings["central_rest_api"]["protocol"] = protocol
    base_url = f"{settings['central_rest_api']['protocol']}://{settings['central_rest_api']['host']}:{settings['central_rest_api']['port']}"

    corpus = CorpusServer(base_url, settings["central_rest_api"]["api_key"], db)
    project = asyncio.run(corpus.get_project(project_id))
    if output_path:
        project.project_path = output_path
    else:

        project.project_path = os.path.join(os.getcwd(), project.project_name)

    os.makedirs(project.project_name, exist_ok=True)
    os.makedirs(os.path.join(project.project_name, "data"), exist_ok=True)

    project.project_data_path = os.path.join(project.project_path, "data")
    file_list = asyncio.run(corpus.get_project_files(project.remote_id))
    file_list = file_list.json()
    temp = {}
    for file in file_list:
        if file["file_category"] not in temp:
            temp[file["file_category"]] = []
        f = ProjectFile(filename=file["name"], path=file["path"], sha1=file["hash"], remote_id=file["id"])
        temp[file["file_category"]].append(f)
    project.project_files = temp
    for i in project.project_files:
        os.makedirs(os.path.join(project.project_data_path, i), exist_ok=True)
        file_list = project.project_files[i]
        for file in file_list:
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
