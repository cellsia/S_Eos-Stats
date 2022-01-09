# python modules
from shapely.geometry import Polygon, MultiPoint
import logging
import shutil
import json
import sys
import os

# cytomine modules
import cytomine
from cytomine.models import ImageInstanceCollection, JobData, AnnotationCollection, Annotation, Project, TermCollection
from cytomine.models.software import JobDataCollection, JobParameterCollection

# software version
__version__ = "1.0.1"

# software config
UPLOAD_RESULTS_SOFTWARE_IMAGE_PARAM = "cytomine_image"
UPLOAD_RESULTS_SOFTWARE_PROJECT_PARAM = "cytomine_id_project"
EOS_STATS_FILENAME = "eos-stats"
EOS_STATS_FILE_TYPE =  "stats"
HD_REGIONS_TERMNAME = "Mayor densidad"


# STEP 1: fetch image detections
def _fetch_job_detections(working_path, parameters):

    job_id = parameters.job_id
    jobdatacol = JobDataCollection().fetch_with_filter(key="job", value=job_id)
    job_data = jobdatacol[0]
    filepath = os.path.join(working_path, "detections.json")
    job_data.download(destination=filepath)

    with open(filepath, "r") as json_file:
        detections = json.load(json_file)
        json_file.close()

    os.remove(filepath)

    points = _convert_rectangles_to_points(detections["rectangles"])

    return points


def _convert_rectangles_to_points(rectangles):

    points = []

    for rectangle in rectangles:

        x0 = rectangle["x0"]
        x1 = rectangle["x1"]
        y0 = rectangle["y0"]
        y1 = rectangle["y1"]
        
        poly = Polygon([[x0,y0],[x1,y0],[x1,y1],[x0,y1]])
        points.append(poly.centroid)

    return points

# STEP 2: fetch image and create grid
def _fetch_image_and_create_grid(parameters):

    job_id = parameters.job_id
    jobparameters = JobParameterCollection().fetch_with_filter(key="job", value=job_id)
    image_param = [p for p in jobparameters if p.name == UPLOAD_RESULTS_SOFTWARE_IMAGE_PARAM][0]
    image_id = image_param.value
    project_param = [p for p in jobparameters if p.name == UPLOAD_RESULTS_SOFTWARE_PROJECT_PARAM][0]
    project_id = project_param.value

    imageinstancecol = ImageInstanceCollection().fetch_with_filter(key="project",value=project_id)
    imageinstance = [image for image in imageinstancecol if image.id == int(image_id)][0]
    
    w = imageinstance.width
    h = imageinstance.height
    res = imageinstance.resolution # micrometro por pixel

    grid_box_side = int(1 / (res * 0.001)) # a cuantos píxeles equivale 1 mm de la imagen
    grid = []

    iteration = grid_box_side / 4 # prefiero superponer boxes a expensas de rendimiento para una mayor precisión

    for x in range(0, w, iteration):
        for y in range(0, h, iteration):

            grid.append(Polygon([[x,y],[x+grid_box_side,y],[x+grid_box_side,y+grid_box_side],[x,y+grid_box_side]]))

    return grid, image_id
    

# STEP 3: calculate the highest density polygon
def _calculate_highest_density_polygon(job_detections, image_grid):

    hd_poly = []
    maxim = 0

    for poly in image_grid:

        inside_points = [p for p in job_detections if poly.contains(p)]
        if len(inside_points) > maxim:
            maxim = len(inside_points)
            hd_poly = []
            hd_poly.append(poly)
        elif len(inside_points) == maxim:
            hd_poly.append(poly)
        else:
            continue

    return hd_poly, maxim


# STEP 4: upload eos-stats file
def _upload_eos_stats_file(job, hd_poly, density):

    eos_stats = {
        "number-of-regions":len(hd_poly),
        "density":density
    }

    # ----- upload stats file -----
    f = open("tmp/"+EOS_STATS_FILENAME, "w+")
    json.dump(eos_stats, f)
    f.close()

    job_data = JobData(job.id, EOS_STATS_FILE_TYPE, EOS_STATS_FILENAME).save()
    job_data.upload("tmp/"+EOS_STATS_FILENAME)
    os.system("rm tmp/"+EOS_STATS_FILENAME)

    return None


# STEP 5: upload hd annotation
def _upload_hd_annotation(job, hd_poly, parameters, image_id):

    project = Project().fetch(job.project)
    termcol = TermCollection().fetch_with_filter("ontology", project.ontology) # fetch term collection ...
    term_id = [t.id for t in termcol if t.name == HD_REGIONS_TERMNAME]

    for poly in hd_poly:
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
        job_detections = _fetch_job_detections(working_path, parameters)
        
        # STEP 2: fetch image and create grid
        image_grid, image_id = _fetch_image_and_create_grid(parameters)

        # STEP 3: calculate the highest density polygon
        hd_poly, density = _calculate_highest_density_polygon(job_detections, image_grid)

        # STEP 4: upload eos-stats file
        _upload_eos_stats_file(job, hd_poly, density)

        # STEP 5: upload hd annotation
        _upload_hd_annotation(job, hd_poly, parameters, image_id)
        



    finally:
        
        logging.info("Deleting folder %s", working_path)
        shutil.rmtree(working_path, ignore_errors=True)
        logging.debug("Leaving run()")

    



if __name__ == '__main__':
    
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)