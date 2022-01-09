# python modules
import logging
import sys

# cytomine modules
import cytomine


# main function 
def run(cyto_job, parameters):
    pass


if __name__ == '__main__':
    
    logging.debug("Command: %s", sys.argv)

    with cytomine.CytomineJob.from_cli(sys.argv) as cyto_job:

        run(cyto_job, cyto_job.parameters)