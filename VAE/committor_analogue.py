# George Miloshevich 2022
#   Adapted from earlier version of Dario Lucente
# This routine is written for one parameter: input folder for VAE weights/ whether VAE is used for dimensionality reduction can vary. It shows us how good the committor of the analog Markov chain works
# The new usage committor.py <folder> 
import os, sys
import pickle
from pathlib import Path
os.environ['TF_XLA_FLAGS'] = '--tf_xla_enable_xla_devices'  # https://stackoverflow.com/questions/65907365/tensorflow-not-creating-xla-devices-tf-xla-enable-xla-devices-not-set


folder = Path(sys.argv[1])  # The name of the folder where the weights have been stored
     
import logging
from colorama import Fore # support colored output in terminal
from colorama import Style
if __name__ == '__main__':
    logger = logging.getLogger()
    logger.handlers = [logging.StreamHandler(sys.stdout)]
else:
    logger = logging.getLogger(__name__)
logger.level = logging.INFO     

import importlib.util
def module_from_file(module_name, file_path): #The code that imports the file which originated the training with all the instructions
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

from importlib import import_module
#foo = import_module(fold_folder+'/Funs.py', package=None)


#folder = './xforanalogs/NA24by48/Z8/yrs500/interT15fw20.1.20lrs4'
foo = module_from_file("foo", f'{folder}/Funs.py')
import pickle
import random as rd  
from scipy.stats import norm
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn import neighbors
from sklearn.metrics import log_loss

tff = foo.tff # tensorflow routines 
ut = foo.ut # utilities
ln = foo.ln #Learn2_new.py
print("==Checking GPU==")
import tensorflow as tf
tf.test.is_gpu_available(
    cuda_only=False, min_cuda_compute_capability=None
)


print("==Checking CUDA==")
tf.test.is_built_with_cuda()

# set spacing of the indentation
ut.indentation_sep = '    '

import numba as nb
from numba import jit,guvectorize,set_num_threads
@guvectorize([(nb.int64,nb.float64[:],nb.int64[:],nb.float64[:],nb.float64[:],nb.int64,
               nb.int64,nb.int64,nb.int64,nb.int64[:,:],nb.int64[:,:],nb.float64[:,:])],
             '(),(n),(m),(p),(q),(),(),(),(),(k,o),(l,j)->(n,m)',nopython=True,target="parallel") # to enable numba parallelism
def CommOnePoint(day,ther,dela, Temp_va, Temp_tr, nn, n_Traj, numsteps, Markov_step, Matr_va, Matr_tr,res): 
    """ Compute committor 
        Function for computing the committor at one point. Input: day=point where committor is computed 
        (state of markov chain), ther= vector of threshold, dela= vector of delays, nn= number of neighbors, 
        Matr=Matix which contains indeces of Markov chain, res= vector where results are stored
    Args:
        day (_int_):            day in the validation set where the Markov chain will start
                                a day implies the temporal coordinates in days of the input from the 0-th year 
                                of the 1000 year long dataset. if day is a list the output will be neatly dressed accordingly
        ther (_float_):         vector descrbing the set of thresholds
        dela (_float_):         vector describing the set of time delays (lead times)
        Temp_va (_float_):      vector containing historical (temperature) time series in validation set
        Temp_tr (_float_):      vector containing historical (temperature) time series in training set
        nn (_int_):             number of nearest neighbors to look for
        n_Traj (_int_):         Number of MC samples that start from the same day (number of trajectories).
        numsteps (_int_):       numbe of steps in the A(t) event (e.g. 15 days with 3 day jumps gives 5)
        Markov_step (_int_):    step in the Markov chain (how many days)
        Matr_va (_ndarray_):    T matrix between validation where we start and training set
        Matr_tr (_ndarray_):    T matrix inside the training set
        res (_float_):          stores the committor (return), this is how numba vectorization forces the output to be treated
    """
    wrong_index = 0 # This checks that during input or execution we were always working with indecies that exist in the considered matrices and we don't go below or above
    if (day >= Matr_va.shape[0]) or (day < 0): # We don't allow inputs that are outside of the range of Matr_va. 
        #print("day > Matr_va.shape[0]")
        wrong_index = 1 # manual debugging (unfortunately numba does not capture this)
        print("We don't allow inputs that are outside of the range of Matr_va")
        for l_1 in range(len(ther)):
            for l_2 in range(len(dela)):
                res[l_1][l_2] = np.nan # we simply  don't have corresponding index
    if nn > Matr_va.shape[1]:
        wrong_index = 1 # manual debugging: use to monitor if we get out of the Matr_tr allowed set
        print("We don't allow inputs that are outside of the range of Matr_va")
    else:
        #print("day <= Matr_va.shape[0]")
        z = np.zeros((len(ther),len(dela))) #auxiliary variable (result)
        for i in range(n_Traj):
            app = rd.randint(0,nn-1) # we go randomly to the training dataset from the validation dataset without updating the time
            s = Matr_va[day][app]
            #print("output: ", day,app,s, Matr_va.shape)
            if (s >= Matr_tr.shape[0]) or (s < 0):
                wrong_index = 1
            A = np.zeros((len(ther),len(dela))) #auxiliary variable (integrated temperature)
            
            for j in range(numsteps+np.max(dela)): 
                if j > 0: # We take the j = 0 case as the initial analog and evolve only the later ones
                    app = rd.randint(0,nn-1) #analogue selection
                    s = Matr_tr[s][app] + Markov_step         #analog state s is evolved in time
                    if (s >= Matr_tr.shape[0]) or (s < 0):
                        wrong_index = 1
                    if nn > Matr_tr.shape[1]:
                        wrong_index = 1 # manual debugging: use to monitor if we get out of the Matr_tr allowed set
                for l_2 in range(len(dela)): 
                    if(j>=dela[l_2] and j<dela[l_2]+numsteps):
                        for l_1 in range(len(ther)):
                            if j > 0: # We take the j = 0 case as the initial state which is already known
                                if (s >= len(Temp_tr)) or (s < 0):
                                    wrong_index = 1
                                else:
                                    A[l_1][l_2] += Temp_tr[s] ## GM: we start counting A only when we get into this delay window
                            else: # We take the j = 0 case as the initial state which is already known. That state is 'day' in validation set
                                if (day >= len(Temp_va)) or (day < 0):
                                    wrong_index = 1
                                else:
                                    A[l_1][l_2] += Temp_va[day] ## GM: we start counting A only when we get into this delay window
            A = A / numsteps 
            
            #Check if A>a
            for l_1 in range(len(ther)):
                for l_2 in range(len(dela)):
                    if(A[l_1][l_2]>ther[l_1]):
                        z[l_1][l_2] += 1.
        if wrong_index == 0:
            #fill res vector
            for l_1 in range(len(ther)):
                for l_2 in range(len(dela)):
                    res[l_1][l_2] = z[l_1][l_2] / n_Traj
        else:
            print("Somewhere inside the code there was an input outside of the range of matrices/vectors")
            for l_1 in range(len(ther)):
                for l_2 in range(len(dela)):
                    res[l_1][l_2] = np.nan # we simply  don't have the corresponding index
                    
@ut.execution_time  # prints the time it takes for the function to run
@ut.indent_logger(logger)   # indents the log messages produced by this function     
def RemoveSelfAnalogs(Matr_tr,n_days):
    """_summary_

    Args:
        Matr_tr (_ndarray_):        T matrix inside the training set
        n_days (_float_):           Keeps track of length of the year (summer) which is expected to be set to time_end-time_start-T+1
                                    We need this object to handle properly the indices and convert between index and year/calendar day   

    Returns:
        ndarray: The new matrix of analogs where self analogs have been shuffled away to the end (columns) of 
        the matrix and then removed, note that there will be missing values if we look for such far away neighbors
    """
    selfanalogues = ((np.arange(Matr_tr.shape[0]//n_days)[np.newaxis].T*np.ones((Matr_tr.shape[0]//n_days,n_days))).astype(int)).flatten()[np.newaxis].T # This is a matrix of years related to the raw index
    sameyear = selfanalogues*np.ones((selfanalogues.shape[0],Matr_tr.shape[1]))==Matr_tr//n_days # A conditional matrix showing if the entry belongs to the same year 
    noselfanalogs = (np.where(sameyear,-1,Matr_tr)) # We set to -1 all the entries that are analogs of the same year
    logger.info(f'Average rate of self analogs: {np.mean(noselfanalogs == -1)}')
    noselfanalogsmoved = []
    for noselfanalogs_row in noselfanalogs: # loop over samples
        temp = np.delete(noselfanalogs_row,noselfanalogs_row==-1) # remove the values equal to -1 
        noselfanalogsmoved.append(np.pad(temp, (0,noselfanalogs_row.shape[0] - temp.shape[0]), constant_values=(noselfanalogs.shape[0],noselfanalogs.shape[0])))  # pad with the length of the time series so that if we accidently get such analog the error will be returned
    noselfanalogsmoved = np.array(noselfanalogsmoved)
    return noselfanalogsmoved
        
@ut.execution_time  # prints the time it takes for the function to run
@ut.indent_logger(logger)   # indents the log messages produced by this function
def RunNeighbors(Matr_va,Matr_tr, time_series_va, time_series_tr, days, threshold, num_Traj=100, T=15, chain_step=3, neighbors=[10], delay=np.arange(6)):
    """Loop through the list of nearest neighbors and run  q[nn] = CommOnePoint

    Args:
        Matr_va (_ndarray_):        T matrix between validation where we start and training set
        Matr_tr (_ndarray_):        T matrix inside the training set
        time_series_va (_float_):   Vector containing historical (temperature) time series in validation set
        time_series_tr (_float_):   Vector containing historical (temperature) time series in training set
        days (_int_):               Vector of days to start the simulation from
        threshold (_float_):        Vector describing the set of thresholds
        num_Traj (int, optional):   Number of MC samples that start from the same day (number of trajectories). Defaults to 100.
        T (int, optional):          Number of days in A(t) event. Defaults to 15.
        chain_step (int, optional): How many days the Markov chain jumps over each iteration. Defaults to 3.
        neighbors (list, optional): Number of nearest neihbors. Defaults to [10].
        dela (_float_, optional):   vector describing the set of time delays (lead times
    Returns:
        _type_: _description_
    """
    N_Steps = T//chain_step
    logger.info(f'{num_Traj = }, {N_Steps = }, {chain_step = }, {T = }, {neighbors = }, {delay = }, {threshold = }')
    q = {}
    for nn in neighbors:
        logger.info(f'{nn = }')
        q[nn] = CommOnePoint(days,threshold,delay,time_series_va,time_series_tr,nn,num_Traj, N_Steps, chain_step, Matr_va,Matr_tr)
    if hasattr(q[nn],'shape'):
        logger.info(f'{q[nn].shape = }')
    return q

@ut.execution_time  # prints the time it takes for the function to run
@ut.indent_logger(logger)   # indents the log messages produced by this function
def RunCheckpoints(ind_new_va,ind_new_tr,time_series_va, time_series_tr, threshold, n_days, 
                   start_calendar_day=None, start_day_set='va', allowselfanalogs=False, RunNeighbors_kwargs = None):
    """Run each checkpoint: Note that when using only one layer for geopotential ('keep_dims' : [1] in run_vae_kwargs) 
        it is understood that checkpoint corresond to different values of the geopotential coefficient in the metric

    Args:
        ind_new_va (darray):        Contains dictionary where each item corresponds to the validation T matrix
                                    indexed by the key corresponding to checkpoint. For details see header of this summary
        ind_new_tr (darray):        Contains dictionary where each item corresponds to the training T matrix
                                    indexed by the key corresponding to checkpoint. For details see header of this summary
        time_series_va (_float_):   vector containing historical (temperature) time series in validation set
        time_series_tr (_float_):   vector containing historical (temperature) time series in training set
        threshold (_float_):        vector descrbing the set of thresholds
        n_days (_float_):           Keeps track of length of the year (summer) which is expected to be set to time_end-time_start-T+1
                                    We need this object to handle properly the indices and convert between index and year/calendar day  
        start_calendar_day (_int_, optional): If not None then it is interpreted as a calendar day of days to retain. Defaults to None.
        start_day_set (str, optional): If we want to start in the training set it is necessary to set it to 'tr'. Defaults to 'va'.
        allowselfanalogs (bool, optional): Deside whether the analogs from the same year are allowed. Defaults to False.
        RunNeighbors_kwargs (_type_, optional): see kwargs of function RunNeighbors() for explanation. Defaults to None.

    Returns:
        _type_: _description_
    """
    if RunNeighbors_kwargs is None:
        RunNeighbors_kwargs = {}
   
    q = {}
    for checkpoint in ind_new_tr.keys():
        logger.info(f'{checkpoint = }')
        if allowselfanalogs:
            Matr_tr = ind_new_tr[checkpoint]
        else:
            Matr_tr = RemoveSelfAnalogs(ind_new_tr[checkpoint],n_days)
        Matr_va = ind_new_va[checkpoint]
        logger.info(f"{Matr_va.shape = }")
        if start_day_set == 'va': # by default we initialize days from the validation set
            days = np.arange(Matr_va.shape[0]) # by default we take the whole validation set
        else:
            days = np.arange(Matr_tr.shape[0]) # by default we take the whole training set
        if start_calendar_day is not None:
            days = days.reshape(-1,n_days)[:,start_calendar_day].reshape(-1)
            print(f'{days.shape = }')
        # Note that we will compute committor on all days available (i.e. the ones which have been assign index in the T matrix)
        # Later we may choose to use only relevant days when evaluating the skill (see ComputeSkill())
        q[checkpoint] = RunNeighbors(Matr_va, Matr_tr, time_series_va, time_series_tr, days, threshold, **RunNeighbors_kwargs)
    return q

@ut.execution_time  # prints the time it takes for the function to run
@ut.indent_logger(logger)   # indents the log messages produced by this function
def RunFolds(folder,nfolds, threshold, n_days, nfield=0, input_set='va', bulk_set='tr', RunCheckpoints_kwargs=None):
    """Loop through folds and run q[fold] = RunCheckpoints

    Args:
        folder (_string_):          name of the folder where the data are stored
        nfolds (_int_):             number of folds, which is typically 10
        threshold (_float_):        vector descrbing the set of thresholds
        n_days (_float_):           Keeps track of length of the year (summer) which is expected to be set to time_end-time_start-T+1
                                    We need this object to handle properly the indices and convert between index and year/calendar day    
        nfield (int, optional):     The time series are stored with an index of a field, typically integrals of (t2m,zg500,mrso). 
                                    If we pick 0 we get t2m. Defaults to 0.
        input_set (str, optional):  Tells whether to assign Matr_va to the validation set or not. Defaults to 'va'.
        bulk_set (str, optional):   Tells whether to assign Matr_tra to the training set or not. . Defaults to 'tr'.
        RunCheckpoints_kwargs (_type_, optional): See details in RunCheckpoints(). Defaults to None.

    Returns:
        _darray_: array of committor values
    """
    if RunCheckpoints_kwargs is None:
        RunCheckpoints_kwargs = {}
    q = {}
    for fold in range(nfolds):
        logger.info(f'{fold = }, loading from {folder}/fold_{fold}/analogues.pkl')
        # the rest of the code goes here
        with open(f'{folder}/fold_{fold}/analogues.pkl', "rb") as open_file:
            analogues = pickle.load(open_file)
        
        time_series = {}
        time_series[bulk_set] = np.load(f"{folder}/fold_{fold}/time_series_{bulk_set}.npy")[:,nfield] # We extract only the temperature
        time_series[input_set] = np.load(f"{folder}/fold_{fold}/time_series_{input_set}.npy")[:,nfield]
        
        q[fold] = RunCheckpoints(analogues[f'ind_new_{input_set}'],analogues[f'ind_new_{bulk_set}'],time_series[input_set], time_series[bulk_set] , threshold, n_days, **RunCheckpoints_kwargs)
    return q


@ut.execution_time  # prints the time it takes for the function to run
@ut.indent_logger(logger)   # indents the log messages produced by this function
def ComputeSkill(folder, q, percent, chain_step):
    logger.info(f'Using {chain_step}')
    committor = dict()
    skill = dict()
    for i, qfold in q.items():
        Y_va = (np.load(f"{folder}/fold_{i}/Y_va.npy").reshape(-1,n_days)
                [:,(label_period_start-time_start):(n_days-T+1)]).reshape(-1) # the goal is to extract only the summer heatwaves
        logger.info(f'Extraction from {label_period_start-time_start = } to {(n_days-T+1)} and reshape(-1) gives  {Y_va.shape = }')
        for j, qcheckpoints in qfold.items():
            if j not in committor:
                committor[j] = {}
            if j not in skill:
                skill[j] = {}
            for k, qneighbors in qcheckpoints.items():
                if k not in committor[j]:
                    temp = dict()
                else:
                    temp = committor[j][k]
                temp[i] = np.squeeze(qneighbors) 
                committor[j][k] = temp
                if k not in skill[j]:
                    temp2 = dict()
                else:
                    temp2 = skill[j][k]
                temp2[i] = []
                for l in range(temp[i].shape[1]): # loop over the tau dimension
                    #logger.info(f'{Y_va.shape = },{temp[i][:,l].shape = }, {label_period_start-time_start-3*l = }, {n_days-T+1-3*l = }, {n_days = }  ')
                    # the goal is to extract only the summer heatwaves, but the committor is computed from mid may 
                    # to the end of August. For tau = 0 we should have from June1 to August15 and for increasing
                    # tau this window has to shift towards earlier dates
                    entropy = tf.keras.losses.BinaryCrossentropy(from_logits= 
                                False)(Y_va, (temp[i][:,l].reshape(-1,n_days)[:,(label_period_start-
                                time_start-3*l):(n_days-T+1-3*l)]).reshape(-1)).numpy() 
                    maxskill = -(percent/100.)*np.log(percent/100.)-(1-percent/100.)*np.log(1-percent/100.)
                    temp2[i].append((maxskill-entropy)/maxskill) # Using 3 instead of chain_step is important because tau increments are still 3 days 
                skill[j][k] = temp2
    logger.info("Computed the skill of the committor")

    """     If you want to concatenate the     
    for j, qcheckpoints in committor.items():
        for k, qneighbors in qcheckpoints.items():
            committor[j][k] = (np.concatenate(list(qneighbors.values()),axis=0).shape
    """
                
    logger.info(f"Computed skill score for the committor and saving in {folder}/committor.pkl")
    committor_file = open(f'{folder}/committor.pkl', "wb")
    pickle.dump({'committor' : committor, 'skill' : skill, 'RunFolds_kwargs_default' : RunFolds_kwargs_default}, committor_file)
    committor_file.close()
    
    return committor, entropy

ln.RunCheckpoints = RunCheckpoints
ln.RunNeighbors = RunNeighbors
ln.RunFolds = RunFolds


#from tensorflow.keras.preprocessing.image import ImageDataGenerator
sys.path.insert(1, '../ERA')

if __name__ == '__main__': #  so that the functions above can be used in trajectory_analogue.py
    year_permutation = np.load(f'{folder}/year_permutation.npy')
    run_vae_kwargs = ut.json2dict(f"{folder}/config.json")
    T = ut.extract_nested(run_vae_kwargs, 'T')
    if (ut.keys_exists(run_vae_kwargs, 'label_period_start') and ut.keys_exists(run_vae_kwargs, 'label_period_end')):
        label_period_start = ut.extract_nested(run_vae_kwargs, 'label_period_start')
        label_period_end = ut.extract_nested(run_vae_kwargs, 'label_period_end')
        time_start = ut.extract_nested(run_vae_kwargs, 'time_start')
        time_end = ut.extract_nested(run_vae_kwargs, 'time_end')
    threshold = np.array([np.load(f'{folder}/threshold.npy')]) #Threshold defining committor. This parameter I don't need, I shall perhaps transform it into epochs for variational autoencoder 
    percent = ut.extract_nested(run_vae_kwargs, 'percent')
    nfolds = ut.extract_nested(run_vae_kwargs, 'nfolds')
    n_days = time_end-time_start-T+1   
    logger.info(f"{Style.RESET_ALL}")

    extra_day=1
    if ut.keys_exists(run_vae_kwargs, 'A_weights'):
        A_weights = ut.extract_nested(run_vae_kwargs, 'A_weights')
        if A_weights is not None:
            extra_day = A_weights[0] # We need to see if the labels were interpolated to see how much the algorithm should jump each summer
    if extra_day == 3:
        delay = np.arange(6)
    else:
        delay = 3*np.arange(6)

    RunFolds_kwargs_default = ln.get_default_params(RunFolds, recursive=True)
    RunFolds_kwargs_default = ut.set_values_recursive(
        RunFolds_kwargs_default, {'num_Traj' : 10000, 'chain_step' : extra_day, 'delay' : delay, 'neighbors' : [2,3,5,10,20,50], 
                                'T' : T, 'allowselfanalogs' : True, 'input_set' : 'va', 'bulk_set' : 'tr'}  )

    chain_step = ut.extract_nested(RunFolds_kwargs_default, 'chain_step')  
    logger.info(RunFolds_kwargs_default)
    logger.info(f"{Fore.BLUE}") #  indicates we are inside the routine 
    time_series_tr_0 = np.load(f"{folder}/fold_{0}/time_series_tr.npy")[:,0]
    time_series_va_0 = np.load(f"{folder}/fold_{0}/time_series_va.npy")[:,0]
    with open(f'{folder}/fold_{0}/analogues.pkl', "rb") as open_file:
        analog = pickle.load(open_file)
    analogues_va = list(analog['ind_new_va'].values())[0] # Here we need to load just random analogs for the compilation below
    analogues_tr = list(analog['ind_new_tr'].values())[0]
    #analogues_tr = (pickle.load(open_file)['ind_new_tr'][10])

    CommOnePoint(33,threshold,delay,time_series_va_0,time_series_tr_0,[2,3,5,10,20,50],10, 5, chain_step, 
                analogues_va,analogues_tr) # We have to compile the numba function before it can be used in parallel
    q = RunFolds(folder,nfolds, threshold, n_days, **RunFolds_kwargs_default)   # Full run

    committor, entropy = ComputeSkill(folder, q, percent, chain_step)

    logger.info(f"{Style.RESET_ALL}")