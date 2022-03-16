# python modules
from shapely.geometry import Polygon
import logging
import shutil
import json
import sys
import os

# cytomine modules
import cytomine
from cytomine.models import JobData, AnnotationCollection, Annotation, Project, TermCollection
from cytomine.models.software import JobDataCollection, JobParameterCollection

# software version
__version__ = "1.1.5"

# software config
EOS_STATS_FILENAME = "eos-stats.json"
EOS_STATS_FILETYPE =  "stats"
HD_REGIONS_TERMNAME = "Mayor densidad"
MICROABS_TERMNAME = "Microabscesos"
UPLOAD_RESULTS_SOFTWARE_IMAGE_PARAM = "cytomine_image"



# STEP 1: fetch diag
def _fetch_job_diag(working_path, parameters):

    job_id = parameters.job_id
    jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)
    job_data = jobdatacol[0]
    filepath = os.path.join(working_path, "detections.json")
    job_data.download(destination=filepath)

    with open(filepath, "r") as json_file:
        detections = json.load(json_file)
        json_file.close()

    os.remove(filepath)

    diag = detections["diag"]
    return diag


# STEP 2: upload diag as stats file
def _upload_diag_file(job, diag) -> None:

    eos_stats = diag

    # ----- upload stats file -----
    f = open("tmp/"+EOS_STATS_FILENAME, "w+")
    json.dump(eos_stats, f)
    f.close()

    job_data = JobData(job.id, EOS_STATS_FILETYPE, EOS_STATS_FILENAME).save()
    job_data.upload("tmp/"+EOS_STATS_FILENAME)
    os.system("rm tmp/"+EOS_STATS_FILENAME)

# STEP 3: upload hd annotation
def _upload_hd_annotation(job, diag, parameters):

    job_id = parameters.job_id
    jobparameters = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
    image_param = [p for p in jobparameters if p.name == UPLOAD_RESULTS_SOFTWARE_IMAGE_PARAM][0]
    image_id = image_param.value 

    project = Project().fetch(job.project)
    termcol = TermCollection().fetch_with_filter("ontology", project.ontology) # fetch term collection ...
    term_id = [t.id for t in termcol if t.name == HD_REGIONS_TERMNAME]

    hd_poly = [Polygon(points) for points in diag["hd_polygons"]]


    # for poly in hd_poly:
    #     annotations = AnnotationCollection()
    #     annotations.append(Annotation(location=poly.wkt, id_image=image_id, id_project=job.project, id_terms=term_id))
    #     annotations.save()

    if len(hd_poly) > 0: 
        poly = hd_poly[0]
        annotations = AnnotationCollection()
        annotations.append(Annotation(location=poly.wkt, id_image=image_id, id_project=job.project, id_terms=term_id))
        annotations.save()

    microabs = [Polygon(points) for points in diag["microabs"]]
    project = Project().fetch(job.project)
    termcol = TermCollection().fetch_with_filter("ontology", project.ontology) # fetch term collection ...
    term_id = [t.id for t in termcol if t.name == MICROABS_TERMNAME]
    
    
    if len(microabs) > 0: 
        for poly in microabs:
            annotations = AnnotationCollection()
            annotations.append(Annotation(location=poly.wkt, id_image=image_id, id_project=job.project, id_terms=term_id))
            annotations.save()

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
        diag = _fetch_job_diag(working_path, parameters)

        # STEP 2: upload diag as stats file
        _upload_diag_file(job, diag)

        # STEP 5: upload hd annotation
        _upload_hd_annotation(job, diag, parameters)
        



    finally:
        
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

    



if __name__ == '__main__':
    
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)