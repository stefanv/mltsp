#!/usr/bin/python

import glob
from parse import parse
import lc_tools
from subprocess import call, Popen, PIPE
import sys, os, inspect
import cPickle
import cfg
import uuid
import shutil

class MissingRequiredParameterError(Exception):
    '''Exception that is raised when a required parameter is not provided in a function call.
    '''
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return str(self.value)



class MissingRequiredReturnKeyError(Exception):
    '''Exception raised when a function reports that it returns a certain parameter but does not in fact return it.
    '''
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return str(self.value)




class myFeature(object):
    '''
    '''
    def __init__(self,requires,provides):
        """
        'requires' must be a list of variable names required by the function, 'provides' 
        must be a list of the key names of the returned dictionary - the features calculated by 
        a particular function
        'requires' and 'provides' are set as attributes.
        """
        self.requires=requires
        self.provides=provides
    
    def __call__(self,f):
        def wrapped_f(*args,**kwargs):
            for required_arg in self.requires:
                if required_arg not in args and required_arg not in kwargs:
                    raise MissingRequiredParameterError("Required arg %s not provided in function call." % required_arg)
            result_dict = f(*args,**kwargs)
            for provided in self.provides:
                if provided not in result_dict:
                    raise MissingRequiredReturnKeyError("Key %s not present in function return value." % provided)
            return result_dict
        return wrapped_f



class DummyFile(object):
    def write(self, x): pass





def execute_functions_in_order(script_fname='testfeature1.py',features_already_known={"t":[1,2,3],"m":[1,23,2],"e":[0.2,0.3,0.2],"coords":[22,33]},script_fpath="here"):
    ''' Parses the script (which must have function definitions with decorators specifying the 
        required parameters and those which are provided by each function) and executes the 
        functions defined in that script such that all functions whose outputs are required 
        as inputs of other functions are called first...
    '''
    # for docker container:
    import sys
    sys.path.append("/home/mltp")
    
    
    if script_fpath != "here":
        import sys
        sys.path.append(script_fpath.replace("/"+script_fname,""))
    else:
        script_fpath = script_fname
    thismodule = __import__(script_fname.replace(".py",""))
    try:
        with open(script_fpath) as f:
            all_lines = f.readlines()
    except IOError:
        with open("/home/mltp/"+script_fname) as f:
            all_lines = f.readlines()
    
    
    fnames_req_prov_dict = {}
    all_required_params = []
    all_provided_params = []
    for i in range(len(all_lines)-1):
        if "@myFeature" in all_lines[i] and "def " in all_lines[i+1]:
            reqs_provs_1 = parse("@myFeature(requires={requires}, provides={provides})",all_lines[i].strip())
            func_name = parse("def {funcname}({args}):", all_lines[i+1].strip())
            fnames_req_prov_dict[func_name.named['funcname']] = {"requires":eval(reqs_provs_1.named["requires"]),"provides":eval(reqs_provs_1.named["provides"])}
            all_required_params = list(set(all_required_params + list(set(eval(reqs_provs_1.named["requires"])))))
            all_provided_params = list(set(all_provided_params + list(set(eval(reqs_provs_1.named["provides"])))))
    all_required_params = [x for x in all_required_params if x not in features_already_known]
    for reqd_param in all_required_params:
        if reqd_param not in all_provided_params:
            raise Exception("Not all of the required parameters are provided by the functions in this script (required parameter '%s')."%str(reqd_param))
    
    
    funcs_round_1 = []
    func_queue = []
    funcnames = fnames_req_prov_dict.keys()
    i=0
    func_rounds = {}
    
    
    all_extracted_features = {}
    
    # redirect stdout temporarily:
    save_stdout = sys.stdout
    sys.stdout = DummyFile()
    
    while len(funcnames) > 0:
        func_rounds[str(i)] = []
        for funcname in funcnames:
            reqs_provs_dict = fnames_req_prov_dict[funcname]
            reqs = reqs_provs_dict['requires']
            provs = reqs_provs_dict['provides']
            
            if len(set(all_required_params) & set(reqs)) > 0:
                func_queue.append(funcname)
            else:
                func_rounds[str(i)].append(funcname)
                all_required_params = [x for x in all_required_params if x not in provs]
                arguments = {}
                for req in reqs:
                    if req in features_already_known:
                        arguments[req] = features_already_known[req]
                    elif req in all_extracted_features:
                        arguments[req] = all_extracted_features[req]
                func_result = getattr(thismodule, funcname)(**arguments)
                all_extracted_features = dict(all_extracted_features.items() + func_result.items())
                funcnames.remove(funcname)
        i+=1
    
    sys.stdout = save_stdout
    
    return all_extracted_features
    
    
    



def docker_installed():
    from subprocess import call, PIPE
    try:
        
        x=call(["docker"], stdout=PIPE,stderr=PIPE)
        return True
    except OSError:
        return False



def docker_extract_features(script_fpath,features_already_known={},ts_datafile_path=None,ts_data=None):
    '''
    Spins up / runs a docker container which does all the script excecution/feature extraction inside,
    and whose output is captured and returned here. 
    
    Input parameters:
        - ts_datafile_path
        - ts_data must be either list of lists or tuples each containing t,m(,e) for a single epoch or None,
            in which case ts_datafile_path must not be None
    '''
    
    if "t" not in features_already_known or "m" not in features_already_known: ## get ts data and put into features_already_known
    
        if ts_datafile_path is None and ts_data is None:
            raise ValueError("No time series data provided! ts_datafile_path is None and ts_data is None  !!")
        
        tme = []
        if ts_datafile_path: # path to ts data file
            # parse ts data and put t,m(,e) into features_already_known
            with open(ts_datafile_path) as f:
                all_lines = f.readlines()
            for i in range(len(all_lines)):
                if all_lines[i].strip() == "":
                    continue
                else:
                    tme.append(all_lines[i].strip().split(","))
            
            
        else: # ts_data passed directly
            # parse ts data and put t,m(,e) into features_already_known
            if type(ts_data) == list:
                if len(ts_data) > 0:
                    if type(ts_data[0]) in [list, tuple] and type(ts_data[0][0]) == float: # ts_data already in desired format
                        tme = ts_data
                    elif type(ts_data[0]) == str and "," in ts_data[0]:
                        for el in ts_data:
                            if el not in ["\n",""]:
                                tme.append(el.split(","))
                else:
                    raise ValueError("ts_data is an empty list")
            elif type(ts_data) == str:
                all_lines = ts_data.strip().split("\n")
                for i in range(len(all_lines)):
                    if all_lines[i].strip() == "":
                        continue
                    else:
                        tme.append(all_lines[i].strip().split(","))
        
        if len(tme) > 0:
            if all(len(this_tme) == 3 for this_tme in tme):
                T,M,E = zip(*tme)
                T = [float(el) for el in T]
                M = [float(el) for el in M]
                E = [float(el) for el in E]
                features_already_known["t"] = T
                features_already_known["m"] = M
                features_already_known["e"] = E
            elif all(len(this_tme) == 2 for this_tme in tme):
                T,M = zip(*tme)
                T = [float(el) for el in T]
                M = [float(el) for el in M]
                features_already_known["t"] = T
                features_already_known["m"] = M
            else:
                raise Exception("custom_feature_tools.py - docker_extract_features() - not all elements of tme are the same length.")
    
    container_name = str(uuid.uuid4())[:10]
    path_to_tmp_dir = os.path.join("/tmp", container_name)
    os.mkdir(path_to_tmp_dir)
    
    
    # copy custom features defs script and pickle the relevant tsdata file into docker temp directory
    status_code = call(["cp", script_fpath, os.path.join(path_to_tmp_dir, "custom_feature_defs.py")])
    with open(os.path.join(path_to_tmp_dir, "features_already_known.pkl"), "wb") as f:
        cPickle.dump(features_already_known,f)
    
    try:
        # the (linux) command to run our docker container which will automatically generate features:
        cmd = ["docker", "run", 
                "-v", "%s:/home/mltp" % cfg.PROJECT_PATH, 
                "-v", "%s:/home/mltp/copied_data_files" % path_to_tmp_dir, 
                "--name=%s" % container_name, 
                "extract_custom_features"]
        # execute command
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        # grab outputs
        stdout, stderr = process.communicate()
        
        print "\n\ndocker container stdout:\n\n", stdout, "\n\ndocker container stderr:\n\n", stderr, "\n\n"
        
        # copy all necessary files produced in docker container to host
        cmd = ["docker", "cp", "%s:/tmp/results_dict.pkl" % container_name, path_to_tmp_dir]
        status_code = call(cmd, stdout=PIPE, stderr=PIPE)
        print "/tmp/results_dict.pkl", "copied to host machine - status code %s" % str(status_code)
        
        # load results from copied .pkl file
        with open(os.path.join(path_to_tmp_dir, "results_dict.pkl"), "rb") as f:
            results_dict = cPickle.load(f)
    except:
        raise
        
    finally:
        
        # Delete used container
        cmd = ["docker", "rm", "-f", container_name]
        status_code = call(cmd)#, stdout=PIPE, stderr=PIPE)
        print "Docker container deleted."
        
        # Remove tmp dir
        shutil.rmtree(path_to_tmp_dir,ignore_errors=True)
    
    
    return results_dict






def test_new_script(script_fname='testfeature1.py', script_fpath="here",docker_container=False):
    if script_fpath == "here":
        script_fpath = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))), script_fname)
    features_already_known_list = []
    all_fnames = False
    try:
        all_fnames = glob.glob(os.path.join(cfg.PROJECT_PATH, ".sample_lcs/dotastro_*.dat"))[:1]
    except:
        pass
            
    if is_running_in_docker_container()==True and (not all_fnames or len(all_fnames)==0) and False:
        try:
            all_fnames = glob.glob("/home/mltp/.sample_lcs/dotastro_*.dat")[:1]
        except:
            all_fnames = False
    if not all_fnames or len(all_fnames)==0:
        print "all_fnames:", all_fnames
        raise Exception("No test lc files read in...")
    else:
        for fname in all_fnames:
            t,m,e = parse_csv_file(fname)
            features_already_known_list.append({"t":t,"m":m,"e":e,"coords":[0,0]})
    
    features_already_known_list.append({"t":[1,2,3],"m":[50,51,52],"e":[0.3,0.2,0.4],"coords":[-11,-55]})
    
    features_already_known_list.append({"t":[1],"m":[50],"e":[0.3],"coords":2})
    
    all_extracted_features_list = []
    
    
    for known_featset in features_already_known_list:
        if docker_installed()==True:
            print "Extracting features inside docker container..."
            newfeats = docker_extract_features(script_fpath=script_fpath,features_already_known=known_featset)
        else:
            newfeats = execute_functions_in_order(script_fname=script_fname,features_already_known=known_featset,script_fpath=script_fpath)
        all_extracted_features_list.append(newfeats)
    
    return all_extracted_features_list
    


def list_features_provided(script_fpath):
    #script_fname = script_fname.strip().split("/")[-1]
    #with open(os.path.join(os.path.join(cfg.UPLOAD_FOLDER,"custom_feature_scripts/"),script_fname)) as f:
    #   all_lines = f.readlines()
    
    with open(script_fpath) as f:
        all_lines = f.readlines()
    
    fnames_req_prov_dict = {}
    all_required_params = []
    all_provided_params = []
    for i in range(len(all_lines)-1):
        if "@myFeature" in all_lines[i] and "def " in all_lines[i+1]:
            reqs_provs_1 = parse("@myFeature(requires={requires}, provides={provides})",all_lines[i].strip())
            func_name = parse("def {funcname}({args}):", all_lines[i+1].strip())
            fnames_req_prov_dict[func_name.named['funcname']] = {"requires":eval(reqs_provs_1.named["requires"]),"provides":eval(reqs_provs_1.named["provides"])}
            all_required_params = list(set(all_required_params + list(set(eval(reqs_provs_1.named["requires"])))))
            all_provided_params = list(set(all_provided_params + list(set(eval(reqs_provs_1.named["provides"])))))
    
    return all_provided_params



def parse_csv_file(fname,sep=',',skip_lines=0):
    f = open(fname)
    linecount = 0
    t,m,e=[[],[],[]]
    for line in f:
        line=line.strip()
        if linecount >= skip_lines:
            if len(line.split(sep))==3:
                ti,mi,ei = line.split(sep)
                t.append(float(ti)); m.append(float(mi)); e.append(float(ei))
            elif len(line.split(sep))==2:
                ti,mi = line.split(sep)
                t.append(float(ti)); m.append(float(mi))
            else:
                linecount-=1
        linecount+=1
    
    #print linecount-1, "lines of data successfully read."
    f.close()
    return [t,m,e]










def generate_custom_features(custom_script_path,path_to_csv,features_already_known,ts_data=None):
    if path_to_csv not in [None,False]:
        t,m,e = parse_csv_file(path_to_csv)
    elif ts_data not in [None,False]:
        if len(ts_data[0]) == 3:
            t,m,e = zip(*ts_data)
        if len(ts_data[0]) == 2:
            t,m = zip(*ts_data)
    else:
        print "predict_class.predict:"
        print "path_to_csv:", path_to_csv
        print "ts_data:", ts_data
        raise Exception("Neither path_to_csv nor ts_data provided...")
    features_already_known['t'] = t
    features_already_known['m'] = m
    if e and len(e)==len(m):
        features_already_known['e'] = e
    
    if is_running_in_docker_container()==True:
        all_new_features = execute_functions_in_order(script_fname=custom_script_path.split("/")[-1],features_already_known=features_already_known,script_fpath=custom_script_path)
    else:
        if docker_installed() == True:
            print "Generating custom features inside docker container..."
            all_new_features = docker_extract_features(script_fpath=custom_script_path,features_already_known=features_already_known)
        else:
            print "Generating custom features WITHOUT docker container..."
            all_new_features = execute_functions_in_order(script_fname=custom_script_path.split("/")[-1],features_already_known=features_already_known,script_fpath=custom_script_path)
        
    
    return all_new_features






def is_running_in_docker_container():
    import subprocess
    proc = subprocess.Popen(["cat","/proc/1/cgroup"],stdout=subprocess.PIPE)
    output = proc.stdout.read()
    print output
    if "/docker/" in output:
        in_docker_container=True
    else:
        in_docker_container=False
    return in_docker_container







if __name__ == "__main__":
    import subprocess
    import sys
    encoding = sys.stdout.encoding or 'utf-8'
    
    docker_container = is_running_in_docker_container()
    
    x = test_new_script(docker_container=docker_container)
    print(str(x).encode(encoding))
    sys.stdout.write( str(x).encode(encoding) )
    
    if docker_container:
        pass
    


