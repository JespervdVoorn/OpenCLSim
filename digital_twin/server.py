from flask import abort
from flask import Flask
from flask import jsonify
from flask import request
from flask import send_file
from flask_cors import CORS

import simpy
from digital_twin import model
import datetime
import os
import time
import zipfile

import pandas as pd
import glob

import json
import hashlib

app = Flask(__name__)
CORS(app)


@app.route("/")
def main():
    return jsonify(dict(message="Basic Digital Twin Server"))


# Activating the code below results in an internal server error when sending a request to /results...
# @app.route("/results")
# def results():
#     results_dir = "simulations/"
#     filename = "results.zip"
#     create_zipfile(results_dir, filename)
#     return send_file(results_dir + filename, mimetype="zip", attachment_filename=filename, as_attachment=True)


def create_zipfile(directory, filename):
    """Gathers all simulation results into a single zipfile which will be stored under directory/filename"""
    directory = append_file_separator(directory)
    file_types = [
        "activities.csv",
        "dredging_spill.csv",
        "energy_use.csv",
        "equipment.csv",
        "equipment_log.csv",
        "events.csv",
        "locations.csv",
        "simulations.csv"
    ]
    for file_type in file_types:
        df = gather_files(directory, file_type)
        df.to_csv(directory + file_type)

    zipf = zipfile.ZipFile(directory + filename, 'w', zipfile.ZIP_DEFLATED)
    for file_type in file_types:
        zipf.write(directory + file_type)
    zipf.close()


def gather_files(directory, file_type):
    """Gathers the files of the given file type ('locations.csv', 'equipment.csv' etc.) in the directory
    into a single dataframe."""
    directory = append_file_separator(directory)
    files = glob.glob(directory + "*_" + file_type)
    df = pd.DataFrame()
    for file in files:
        content = pd.read_csv(file)
        df = pd.concat([df, content])
    return df


def append_file_separator(directory):
    """Appends a / to the given string if necessary"""
    if len(directory) > 0 and directory[-1] != "/" and directory[-1] != "\\":
        directory += "/"
    return directory


@app.route("/simulate", methods=['POST'])
def simulate():
    """run a simulation"""
    if not request.is_json:
        abort(400, description="content type should be json")
        return

    config = request.get_json(force=True)

    try:
        simulation_result = simulate_from_json(config)
    except ValueError as valerr:
        abort(400, description=str(valerr))
        return
    except Exception as e:
        abort(500, description=str(e))
        return

    return jsonify(simulation_result)


def simulate_from_json(config, tmp_path=""):
    """Create a simulation and run it, based on a json input file.
    The optional tmp_path parameter should only be used for unit tests."""
    if "initialTime" in config:
        simulation_start = datetime.datetime.fromtimestamp(config["initialTime"])
    else:
        simulation_start = datetime.datetime.now()
    env = simpy.Environment(initial_time=time.mktime(simulation_start.timetuple()))

    simulation = model.Simulation(
        env=env,
        name="server simulation",
        sites=config["sites"],
        equipment=config["equipment"],
        activities=config["activities"]
    )
    env.run()

    result = simulation.get_logging()
    result["completionTime"] = env.now

    if "saveSimulation" in config and config["saveSimulation"]:
        save_simulation(config, simulation, tmp_path=tmp_path)

    return result


def save_simulation(config, simulation, tmp_path=""):
    """Save the given simulation. The config is used to produce an md5 hash of its text representation.
    This hash is used as a prefix for the files which are written. This ensures that simulations with the same config
    are written to the same files (although it is not a completely foolproof method, for example changing an equipment
    or location name, does not alter the simulation result, but does alter the config file).
    The optional tmp_path parameter should only be used for unit tests."""

    config_text = json.dumps(config, sort_keys=True).encode("utf-8")
    hash = hashlib.md5(config_text).hexdigest()
    file_prefix = hash + '_'

    path = str(tmp_path)
    if len(path) != 0 and str(path)[-1] != "/":
        path += "/"
    path += "simulations/"
    os.makedirs(path, exist_ok=True)  # create the simulations directory if it does not yet exist
    simulation.save_logs(path, file_prefix)
