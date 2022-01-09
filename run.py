# python modules
import logging
import shutil
import sys
import os

# cytomine modules
import cytomine
from cytomine.models import JobData


__version__ = "0.0.2"


# STEP 1: fetch image detections
def _fetch_job_detections(parameters):

    JobData(parameters.job_id).download()

    


# main function 
def run(cyto_job, parameters):

    logging.info("----- test software v%s -----", __version__)
    logging.info("Entering run(cyto_job=%s, parameters=%s)", cyto_job, parameters)
    
    job = cyto_job.job
    project = cyto_job.project

    working_path = os.path.join("tmp", str(job.id))
    if not os.path.exists(working_path):
        logging.info("Creating working directory: %s", working_path)
        os.makedirs(working_path)

    try:

        # STEP 1: fetch job detections
        image_detections = _fetch_job_detections(parameters)

    finally:
        
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

    



if __name__ == '__main__':
    
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)