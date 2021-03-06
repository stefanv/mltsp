from subprocess import Popen, PIPE, call, check_call
import cfg
import uuid
import cPickle
import shutil
#import dockerpy
import uuid
import sys, os
import rethinkdb as r

def featurize_in_docker_container(headerfile_path, zipfile_path, features_to_use, featureset_key, is_test, already_featurized, custom_script_path):
    arguments = locals()
    #unique name for docker container for later cp and rm commands
    container_name = str(uuid.uuid4())[:10]
    path_to_tmp_dir = os.path.join("/tmp", container_name)
    os.mkdir(path_to_tmp_dir)
    
    # copy relevant data files into temp directory on host to be mounted into container
    if os.path.isfile(str(headerfile_path)):
        status_code = call(["cp", headerfile_path, "%s/%s" % (path_to_tmp_dir, headerfile_path.split("/")[-1])])
        arguments["headerfile_path"] = os.path.join("/home/mltp/copied_data_files",headerfile_path.split("/")[-1])
    if os.path.isfile(str(zipfile_path)):
        status_code = call(["cp", zipfile_path, "%s/%s" % (path_to_tmp_dir, zipfile_path.split("/")[-1])])
        arguments["zipfile_path"] = os.path.join("/home/mltp/copied_data_files",zipfile_path.split("/")[-1])
    if os.path.isfile(str(custom_script_path)):
        status_code = call(["cp", custom_script_path, "%s/%s" % (path_to_tmp_dir, custom_script_path.split("/")[-1])])
        arguments["custom_script_path"] = os.path.join("/home/mltp/copied_data_files",custom_script_path.split("/")[-1])
    
    arguments["path_map"] = {path_to_tmp_dir,"/home/mltp/copied_data_files"}
    with open("%s/function_args.pkl"%path_to_tmp_dir, "wb") as f:
        cPickle.dump(arguments,f)
    
    
    try:
        # run the docker container 
        cmd = ["docker", "run", 
                "-v", "%s:/home/mltp" % cfg.PROJECT_PATH, 
                "-v", "%s:/home/mltp/copied_data_files" % path_to_tmp_dir, 
                "-v", "%s:%s" % (cfg.FEATURES_FOLDER, "/Data/features"), 
                "-v", "%s:%s" % (cfg.UPLOAD_FOLDER, "/Data/flask_uploads"), 
                "-v", "%s:%s" % (cfg.MODELS_FOLDER, "/Data/models"), 
                "--name=%s" % container_name, 
                "featurize"]
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        print "\n\ndocker container stdout:\n\n", stdout, "\n\ndocker container stderr:\n\n", stderr, "\n\n"
    
    
        # copy all necessary files produced in docker container to host (features/models/rdb data (pickled)/etc)
        for file_suffix in ["features.csv", "features_with_classes.csv", "classes.pkl"]:
            cmd = ["docker", "cp", "%s:/tmp/%s_%s" % (container_name, featureset_key, file_suffix), cfg.FEATURES_FOLDER]
            status_code = call(cmd, stdout=PIPE, stderr=PIPE)
            print os.path.join(cfg.FEATURES_FOLDER,"%s_%s"%(featureset_key, file_suffix)), "copied to host machine - status code %s" % str(status_code)
    
        shutil.copy2(os.path.join(cfg.FEATURES_FOLDER,"%s_features_with_classes.csv"%featureset_key), os.path.join(cfg.PROJECT_PATH,"flask/static/data"))
    
        os.remove(os.path.join(cfg.FEATURES_FOLDER,"%s_features_with_classes.csv"%featureset_key))
        
        print "Process complete."
    except:
        raise
    finally:
        
        # delete temp directory and its contents
        shutil.rmtree(path_to_tmp_dir, ignore_errors=True)
        
        # kill and remove the container
        cmd = ["docker", "rm", "-f", container_name]
        status_code = call(cmd)#, stdout=PIPE, stderr=PIPE)
        print "Docker container deleted."
        
    
    return "Featurization complete."
    























def build_model_in_docker_container(featureset_name, featureset_key, model_type):
    arguments = locals()
    #unique name for docker container for later cp and rm commands
    container_name = str(uuid.uuid4())[:10]
    path_to_tmp_dir = os.path.join("/tmp", container_name)
    os.mkdir(path_to_tmp_dir)
    
    # copy relevant data files into docker temp directory on host to be mounted into container
    arguments["path_map"] = {path_to_tmp_dir,"/home/mltp/copied_data_files"}
    with open("%s/function_args.pkl"%path_to_tmp_dir, "wb") as f:
        cPickle.dump(arguments,f)
    
    try:
        # run the docker container 
        cmd = ["docker", "run", 
                "-v", "%s:/home/mltp" % cfg.PROJECT_PATH, 
                "-v", "%s:/home/mltp/copied_data_files" % path_to_tmp_dir, 
                "-v", "%s:%s" % (cfg.FEATURES_FOLDER, "/Data/features"), 
                "-v", "%s:%s" % (cfg.UPLOAD_FOLDER, "/Data/flask_uploads"), 
                "-v", "%s:%s" % (cfg.MODELS_FOLDER, "/Data/models"),  
                "--name=%s" % container_name, 
                "build_model"]
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        print "\n\ndocker container stdout:\n\n", stdout, "\n\ndocker container stderr:\n\n", stderr, "\n\n"
        
        # copy all necessary files produced in docker container to host (features/models/rdb data (pickled)/etc)
        cmd = ["docker", "cp", "%s:/tmp/%s_%s.pkl" % (container_name, featureset_key, model_type), cfg.MODELS_FOLDER]
        #status_code = call(cmd, stdout=PIPE, stderr=PIPE)
        #print os.path.join(cfg.MODELS_FOLDER,"%s_%s.pkl"%(featureset_key, model_type)), "copied to host machine - status code %s" % str(status_code)
        check_call(cmd)
        print os.path.join(cfg.MODELS_FOLDER,"%s_%s.pkl"%(featureset_key, model_type)), "copied to host machine."
        print "Process complete."
    except:
        raise
    finally:
        
        # delete temp directory and its contents on host machine
        shutil.rmtree(path_to_tmp_dir, ignore_errors=True)
        
        # kill and remove the container
        cmd = ["docker", "rm", "-f", container_name]
        status_code = call(cmd)#, stdout=PIPE, stderr=PIPE)
        print "Docker container deleted."
    
    return "Model creation complete. Click the Predict tab to start using it."
    




















def predict_in_docker_container(newpred_file_path,project_name,model_name,model_type,prediction_entry_key,featset_key,sep=",",n_cols_html_table=5,features_already_extracted=None,metadata_file=None,custom_features_script=None):
    arguments = locals()
    container_name = str(uuid.uuid4())[:10]
    path_to_tmp_dir = os.path.join("/tmp", container_name)
    os.mkdir(path_to_tmp_dir)
    
    # copy relevant data files into docker temp directory
    if os.path.isfile(str(newpred_file_path)):
        status_code = call(["cp", newpred_file_path, "%s/%s" % (path_to_tmp_dir, newpred_file_path.split("/")[-1])])
        arguments["newpred_file_path"] = os.path.join("/home/mltp/copied_data_files",newpred_file_path.split("/")[-1])
    if os.path.isfile(str(custom_features_script)):
        status_code = call(["cp", custom_features_script, "%s/%s" % (path_to_tmp_dir, custom_features_script.split("/")[-1])])
        arguments["custom_features_script"] = os.path.join("/home/mltp/copied_data_files",custom_features_script.split("/")[-1])
    if os.path.isfile(str(metadata_file)):
        status_code = call(["cp", metadata_file, "%s/%s" % (path_to_tmp_dir, metadata_file.split("/")[-1])])
        arguments["metadata_file"] = os.path.join("/home/mltp/copied_data_files", metadata_file.split("/")[-1])
    
    arguments["path_map"] = {path_to_tmp_dir,"/home/mltp/copied_data_files"}
    with open("%s/function_args.pkl"%path_to_tmp_dir, "wb") as f:
        cPickle.dump(arguments,f)
    
    try:
    
        cmd = ["docker", "run", 
                "-v", "%s:/home/mltp"%cfg.PROJECT_PATH, 
                "-v", "%s:/home/mltp/copied_data_files"%path_to_tmp_dir, 
                "-v", "%s:%s"%(cfg.FEATURES_FOLDER,"/Data/features"), 
                "-v", "%s:%s"%(cfg.UPLOAD_FOLDER,"/Data/flask_uploads"), 
                "-v", "%s:%s"%(cfg.MODELS_FOLDER,"/Data/models"), 
                "--name=%s"%container_name, 
                "predict"]
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        print "\n\ndocker container stdout:\n\n", stdout, "\n\ndocker container stderr:\n\n", stderr, "\n\n"
        
        
        # copy all necessary files produced in docker container to host (features/models/rdb data (pickled)/etc)
        cmd = ["docker", "cp", "%s:/tmp/%s_pred_results.pkl" % (container_name, prediction_entry_key), "/tmp"]
        status_code = call(cmd, stdout=PIPE, stderr=PIPE)
        print "/tmp/%s_pred_results.pkl"%prediction_entry_key, "copied to host machine - status code %s" % str(status_code)
    
        with open("/tmp/%s_pred_results.pkl"%prediction_entry_key, "rb") as f:
            pred_results_dict = cPickle.load(f)
    
        if type(pred_results_dict) != dict:
            print "run_in_docker_container.predict_in_docker_container() - type(pred_results_dict) ==", type(pred_results_dict)
            print "pred_results_dict:", pred_results_dict
            raise Exception("run_in_docker_container.predict_in_docker_container() error message - type(pred_results_dict) != dict")
        print "Process complete."
    except:
        raise
    finally:
        
        # delete temp directory and its contents
        shutil.rmtree(path_to_tmp_dir, ignore_errors=True)
        
        os.remove("/tmp/%s_pred_results.pkl"%prediction_entry_key)
        
        cmd = ["docker", "rm", "-f", container_name]
        status_code = call(cmd)#, stdout=PIPE, stderr=PIPE)
        
        print "Docker container deleted."
    
    return pred_results_dict
















def disco_test():
    #unique name for docker container for later cp and rm commands
    container_name = str(uuid.uuid4())[:10]
    
    try:
        # run the docker container 
        cmd = ["docker", "run", 
                "-v", "%s:/home/mltp" % cfg.PROJECT_PATH, 
                "--name=%s" % container_name, 
                "disco_test"]
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        print "\n\ndocker container stdout:\n\n", stdout, "\n\ndocker container stderr:\n\n", stderr, "\n\n"
        print "Process complete."
    except:
        raise
    finally:
        
        # kill and remove the container
        cmd = ["docker", "rm", "-f", container_name]
        status_code = call(cmd)#, stdout=PIPE, stderr=PIPE)
        print "Docker container deleted."
        
    
    return "Test complete."
    












