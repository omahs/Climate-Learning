# George Miloshevich 2021
# Perform training

# Importation des librairies
import os as os
import sys
sys.path.insert(1, '../ERA')
from ERA_Fields import* # general routines
from TF_Fields import* # tensorflow routines 
import time
import shutil
import gc
import psutil
from imblearn.over_sampling import RandomOverSampler
from imblearn.under_sampling import RandomUnderSampler
from imblearn.combine import SMOTEENN
from imblearn.pipeline import Pipeline
from operator import mul
from functools import reduce

def custom_CNN(model_input_dim): # This CNN I took from https://www.tensorflow.org/tutorials/images/cnn
    model = models.Sequential()
    model.add(layers.Conv2D(32, (3, 3), input_shape=model_input_dim))
    model.add(BatchNormalization())
    model.add(Activation("relu"))
    model.add(SpatialDropout2D(0.2))
    model.add(layers.MaxPooling2D((2, 2)))

    model.add(layers.Conv2D(64, (3, 3)))
    model.add(BatchNormalization())
    model.add(Activation("relu"))
    model.add(SpatialDropout2D(0.2))
    model.add(layers.MaxPooling2D((2, 2)))

    model.add(layers.Conv2D(64, (3, 3)))
    model.add(BatchNormalization())
    model.add(Activation("relu"))
    model.add(SpatialDropout2D(0.2))

    model.add(layers.Flatten())
    model.add(layers.Dense(64, activation='relu'))
    model.add(layers.Dropout(0.2))
    model.add(layers.Dense(2))
    return model


def probability_model(inputs,input_model): # This function is used to apply softmax to the output of the neural network
    x = input_model(inputs)
    outputs = layers.Softmax()(x)
    return keras.Model(inputs, outputs)

def CNN_layers(input_1):# This CNN is inspired by https://www.tensorflow.org/tutorials/images/cnn
    x = layers.Conv2D(32, (3, 3))(input_1)
    x = BatchNormalization()(x)
    x = Activation("relu")(x)
    x = SpatialDropout2D(0.2)(x)
    x = layers.MaxPooling2D((2, 2))(x)

    x = layers.Conv2D(64, (3, 3))(x)
    x = BatchNormalization()(x)
    x = Activation("relu")(x)
    x = SpatialDropout2D(0.2)(x)
    x = layers.MaxPooling2D((2, 2))(x)

    x = layers.Conv2D(64, (3, 3))(x)
    x = BatchNormalization()(x)
    x = Activation("relu")(x)
    x = SpatialDropout2D(0.2)(x)
    return layers.Flatten()(x)

def bottom_layers(input_1):
    x = layers.Dense(64, activation='relu')(input_1)
    x = layers.Dropout(0.2)(x)
    return layers.Dense(2)(x)


from tensorflow.keras.regularizers import l2
import math
def create_regularized_model(factor, rate, inputshape=(1,)):
    model = tf.keras.models.Sequential([
        #tf.keras.layers.Flatten(input_shape=(8, 8)),     # if the model has a tensor input
        tf.keras.layers.Input(shape=inputshape),                 # if the model has a flat input
        tf.keras.layers.Dense(2, kernel_regularizer=l2(factor))
    ])
    return model


def PrepareData(creation = []):  # if we do not specify creation it automacially creates new folder. If we specify the creation, it should correspond to the folder we are running the file from

    sampling='' #'3hrs' # This chooses whether we want say daily sampling or 3 hour one. Notice that the corresponding NetCDF files are kept in different places
    percent = 5 # 1 

    timesperday = 8 # 3 hour long periods in case we choose this sampling
    if sampling == '3hrs':
        T = 14*timesperday
    else:
        T = 14

    tau = 0 #-5  # lag
    usepipelines = False # if True => Dataset.from_tensor_slices will be used. This is a more advanced method but it takes more RAM and there is a possiblity for memory leaks when repeating training for cross-validation
    fullmetrics = True # If True MCC and confusion matrix will be evaluated during training. This makes training slower!

    Model = 'Plasim'
    area = 'France'
    lon_start = 0
    lon_end = 128
    lat_start = 0 # latitudes start from 90 degrees North Pole
    lat_end = 22


    #myscratch='/scratch/gmiloshe/PLASIM/'  # where we acess .py files and save output
    mylocal='/local/gmiloshe/PLASIM/' #'/local/gmiloshe/PLASIM/'      # where we keep large datasets that need to be loaded
    myscratch=TryLocalSource(mylocal)        # Check if the data is not there and can be found in some other source
    #myscratch=mylocal

    new_mixing = False                     # if set to True the undersampling will also follow the suit
    
    num_years = 8000                       # Select the number of years from the simulation for the analysis


    # If an integer >= 1 is chosen we simply undersample by this rate
    # If a float between 0 and 1 is chosen we select each state with the probability given by this float
    undersampling_factor = 10 # 1 #15 #10 #5 #1 #0.25 #0.15 #0.25
    oversampling_factor = 1 # oversampling_factor = 1 means that oversampling will not be performed
    thefield = 't2m' # Important: this is the field that is used to determine the extrema (important for undersampling) and therefore the label space
    BATCH_SIZE = 1024 # choose this for training so that the chance of encountering positive batches is nonnegligeable
    NUM_EPOCHS = 100 #1000 #20 #200 #50 # number of epochs the training involves
    saveweightseveryblaepoch = 1 # If set to 0 the model will not save weights as it is being trained, otherwise this number will tell us how many epochs it weights until saving
    if saveweightseveryblaepoch > 0:
        ckpt = 'ckpt'
    else:
        cktp = ''

    #checkpoint_name = myscratch+'training/stack_CNN_equalmixed_'+ckpt+'_'+thefield+'France_'+'_with_mrsoArea_'+sampling+'_u'+str(undersampling_factor)+'o'+str(oversampling_factor)+'_LONG'+str(num_years)+'yrs_'+'_per_'+str(percent)+'_tau_'+str(tau)
    #checkpoint_name = myscratch+'training/stack_CNNdeepwide2maxpool_equalmix_'+ckpt+'_'+thefield+'France_'+'_with_t2m_zg500_mrsoFrance_'+sampling+'_22by128_u'+str(undersampling_factor)+'o'+str(oversampling_factor)+'_LONG'+str(num_years)+'yrs_'+'_per_'+str(percent)+'_tau_'+str(tau)
    #checkpoint_name = myscratch+'training/stack_CNN_equalmix_'+ckpt+'_'+thefield+'France_'+'_with_zg500_t2mmrsoFrance_'+sampling+'_22by128_u'+str(undersampling_factor)+'o'+str(oversampling_factor)+'_LONG'+str(num_years)+'yrs_'+'_per_'+str(percent)+'_finetune_tau_'+str(tau)
    #checkpoint_name = myscratch+'training/test'
    checkpoint_name_root = myscratch+'training/stack_CNN_equalmixed_'+ckpt+'_'+thefield+'T'+str(T)+'France_'+'_with_zg500_t2mmrsoFrance_'+sampling+'lr5e-5_u'+str(undersampling_factor)+'o'+str(oversampling_factor)+'_'+str(num_years)+'yrs_'+'_per_'+str(percent)+'_finetune_tau_'
    checkpoint_name = checkpoint_name_root+str(tau)
    checkpoint_name_previous = checkpoint_name_root+str(tau+1)

    print("creation = ", creation)
    if creation == []: # If we are not running from the same directory
        if os.path.exists(checkpoint_name): # Create the directory
            print('folder '+checkpoint_name+' exists. Should I overwrite?')
            if input(" write Y to overwrite, else the execution will stop: ") != "Y":
                sys.exit("User has aborted the program")
        else:
            print('folder '+checkpoint_name+' created')
            os.mkdir(checkpoint_name)

        sys.stdout = Logger(checkpoint_name+'/logger.log')  # Keep a copy of print outputs there
        shutil.copy(__file__, checkpoint_name) # Copy this file to the directory of the training
        dest = shutil.copy(__file__, checkpoint_name+'/Funs.py')
        shutil.copy(myscratch+'../ERA/ERA_Fields.py', checkpoint_name)
        shutil.copy(myscratch+'../ERA/TF_Fields.py', checkpoint_name)
        shutil.copy(myscratch+'History.py', checkpoint_name)
        shutil.copy(myscratch+'Recalc_History.py', checkpoint_name)
        shutil.copy(myscratch+'Recalc_Tau_Metrics.py', checkpoint_name)
        shutil.copy(myscratch+'Metrics.py', checkpoint_name)

    #lat_from = [4,4]     # 18x42
    #lat_to   = [22,22]
    #lon_from = [101,0]
    #lon_to   = [128,15]
    lat_from =  [0,0]   # 22x128
    lat_to =    [22,22]
    lon_from =  [64, 0]
    lon_to =    [128, 64]


    print([percent, T, Model, area, undersampling_factor, lat_from, lat_to, lon_from, lon_to, thefield])

    if sampling == '3hrs':
        Months1 = [0, 0, 0, 0, 0, 0, timesperday*30, timesperday*30, timesperday*30, timesperday*30, timesperday*30, 0, 0, 0]
    else: # if sampling == 'daily'
        Months1 = [0, 0, 0, 0, 0, 0, 30, 30, 30, 30, 30, 0, 0, 0] 
    Tot_Mon1 = list(itertools.accumulate(Months1))

    time_start = Tot_Mon1[6]
    time_end = Tot_Mon1[9] #+(Tot_Mon1[10]-Tot_Mon1[9])//2   # uncomment this if we are to use full summer (including the portion with september due to T days window)

    if sampling == '3hrs': 
        prefix = ''
        file_prefix = '../Climate/'
    else:
        prefix = 'ANO_LONG_'
        file_prefix = ''

    t2m = Plasim_Field('tas',prefix+'tas','Temperature', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)     # if we want to use surface tempeature
    zg500 = Plasim_Field('zg',prefix+'zg500','500 mbar Geopotential', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    #zg300 = Plasim_Field('zg',prefix+'zg300','300 mbar Geopotential', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    mrso = Plasim_Field('mrso',prefix+'mrso','soil moisture', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    #ua300 = Plasim_Field('ua',prefix+'ua300','eastward wind', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    #va300 = Plasim_Field('va',prefix+'va300','northward wind', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    #hfls = Plasim_Field('hfls',prefix+'hfls','surface latent heat flux', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    #hfss = Plasim_Field('hfss',prefix+'hfss','surface sensible heat flux', Model, lat_start, lat_end, lon_start, lon_end,'single',sampling)
    
    t2m.years=8000
    zg500.years=8000
    mrso.years=8000
    
    #ts.load_field(mylocal+file_prefix+'Data_Plasim/')  # load the data
    t2m.load_field(mylocal+file_prefix+'Data_Plasim_LONG/')  # load the data
    zg500.load_field(mylocal+file_prefix+'Data_Plasim_LONG/')
    #zg300.load_field(mylocal+file_prefix+'Data_Plasim/')
    mrso.load_field(mylocal+file_prefix+'Data_Plasim_LONG/')
    #ua300.load_field(mylocal+file_prefix+'Data_Plasim/')
    #va300.load_field(mylocal+file_prefix+'Data_Plasim/')
    #hfls.load_field(mylocal+file_prefix+'Data_Plasim/')
    #hfss.load_field(mylocal+file_prefix+'Data_Plasim/')
    
    LON = t2m.LON
    LAT = t2m.LAT
    print(t2m.var.dtype,t2m.var.dtype,t2m.var.dtype)

    mask, cell_area, lsm = ExtractAreaWithMask(mylocal,Model,area) # extract land sea mask and multiply it by cell area
    print(mask)

    #ts.abs_area_int, ts.ano_area_int = ts.Set_area_integral(area,mask)
    t2m.abs_area_int, t2m.ano_area_int = t2m.Set_area_integral(area,mask,'PostprocLONG')
    zg500.abs_area_int, zg500.ano_area_int = zg500.Set_area_integral(area,mask,'PostprocLONG') 
    #zg300.abs_area_int, zg300.ano_area_int = zg300.Set_area_integral(area,mask) 
    mrso.abs_area_int, mrso.ano_area_int = mrso.Set_area_integral(area,mask,'PostprocLONG')
    #ua300.abs_area_int, ua300.ano_area_int = ua300.Set_area_integral(area,mask) 
    #va300.abs_area_int, va300.ano_area_int = va300.Set_area_integral(area,mask)
    #hfls.abs_area_int, hfls.ano_area_int = hfls.Set_area_integral(area,mask) 
    #hfss.abs_area_int, hfss.ano_area_int = hfss.Set_area_integral(area,mask)

    
    # ===Below we filter out just the area of France for mrso====
    
    filter_mask = np.zeros((t2m.var.shape[2],t2m.var.shape[3])) # a mask which sets to zero all values
    filter_lat_from = [13, 13]  # defining the domain of 1's
    filter_lat_to = [17, 17] 
    filter_lon_from = [-1, 0] 
    filter_lon_to =  [128, 3] 

    for myiter in range(len(filter_lat_from)): # seting values to 1 in the desired domain
            filter_mask[filter_lat_from[myiter]:filter_lat_to[myiter],filter_lon_from[myiter]:filter_lon_to[myiter]] = 1
                
    mrso.var = mrso.var*filter_mask # applying the filter to set to zero all values outside the domain

    
    if creation == []: # If we are not running from the same directory
        filename_mixing = t2m.PreMixing(new_mixing, 'PostprocLONG',num_years)  # perform mixing (mix batches and years but not days of the same year!)  # NEW MIXING MEANS ALSO NEW UNDERSAMPLING!
        shutil.copy(filename_mixing, checkpoint_name) # move the permutation file that was used to mix 
        zg500.PreMixing(False, 'PostprocLONG',num_years) # IT IS IMPORTANT THAT ALL SUBSEQUENT FIELDS BE MIXED (SHUFFLED) THE SAME WAY, otherwise no synchronization!
        #zg300.PreMixing(False,num_years)
        mrso.PreMixing(False, 'PostprocLONG',num_years)
        
    else:
        filename_mixing = t2m.PreMixing(new_mixing,creation,num_years) # load from the folder that we are calling this file from   # NEW MIXING MEANS ALSO NEW UNDERSAMPLING!
        zg500.PreMixing(False,creation,num_years) # IT IS IMPORTANT THAT ALL SUBSEQUENT FIELDS BE MIXED (SHUFFLED) THE SAME WAY, otherwise no synchronization!
        #zg300.PreMixing(False,creation,num_years)
        mrso.PreMixing(False,creation,num_years)
    print("t2m.var.shape = ", t2m.var.shape)
    print("time_end = ", time_end, " ,time_start = ", time_start, " ,T = ", T)
    
    A, A_reshape, threshold, list_extremes, convseq =  t2m.ComputeTimeAverage(time_start,time_end,T,tau, percent)
    print("threshold = ",threshold)
    
    if creation == []: # If we are not running from the same directory
        filename_mixing = t2m.EqualMixing(A, threshold, new_mixing, 'PostprocLONG',num_years)
        shutil.copy(filename_mixing, checkpoint_name) # move the permutation file that was used to mix 
        zg500.EqualMixing(A, threshold, False, 'PostprocLONG',num_years) #IT IS IMPORTANT THAT ALL SUBSEQUENT FIELDS BE MIXED (SHUFFLED) THE SAME WAY, otherwise no synchronization!
        #zg300.EqualMixing(A, threshold, False, containing_folder='Postproc',num_years)
        mrso.EqualMixing(A, threshold, False, 'PostprocLONG',num_years)
    else:
        filename_mixing = t2m.EqualMixing(A, threshold, new_mixing,creation,num_years)
        zg500.EqualMixing(A, threshold, False,creation,num_years)
        #zg300.EqualMixing(A, threshold, False,creation,num_years)
        mrso.EqualMixing(A, threshold, False,creation,num_years)
    # Now we have to recompute the extremes:
    
    A, A_reshape, threshold, list_extremes, convseq =  t2m.ComputeTimeAverage(time_start,time_end,T,tau, percent)
    
    # ===== Applying filter to the temperature field: ====
    t2m.var = t2m.var*filter_mask # applying the filter to set to zero all values outside the domain
    
    print("threshold = ",threshold)
    print(A.dtype)
    # Below we reshape into time by flattened array
    t2m.abs_area_int_reshape = t2m.ReshapeInto1Dseries(area, mask, Tot_Mon1[6], Tot_Mon1[9], T, tau)
    mrso.abs_area_int_reshape = mrso.ReshapeInto1Dseries(area, mask, Tot_Mon1[6], Tot_Mon1[9], T, tau)
    print("mrso.abs_area_int_reshape.shape = ", mrso.abs_area_int_reshape.shape)

    print("t2m.var.shape = ", t2m.var.shape)

    #X = mrso.abs_area_int_reshape[:,np.newaxis]


    # Below we reshape into time by flattened array
    #Xs = [t2m.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    #                   If only 2m temperature is used the following command is to be used: (1D representation)
    #
    #X = np.concatenate(Xs, axis=1)
    #                   If we want to include soil moisture integrated over the area the following command is to be used:
    #   (1D representation)
    #X = np.c_[mrso.abs_area_int_reshape[:,np.newaxis],np.concatenate(Xs, axis=1)]
    #
    # Below we reshape into a timex 2D array (space)

    #Xs = [t2m.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    #X = np.concatenate(Xs, axis=2)



    #============== Use this if only one field needs to be used:===========
    ##Xs = [zg500.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##Xs = [mrso.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##Xs = [t2m.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X = np.concatenate(Xs, axis=2)
    ##X = X[:,:,:,np.newaxis]

    # =================Use this if many fields need to be used:============

    Xs = [t2m.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    X = np.concatenate(Xs, axis=2)
    

    ## Without Coarse Graining:
    Xs = [zg500.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    X= np.concatenate([X[:,:,:,np.newaxis], np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    
    Xs = [mrso.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    
    ## Use below for fused networks
    #X = [X, mrso.abs_area_int_reshape[:,np.newaxis]]#, t2m.abs_area_int_reshape[:,np.newaxis]]


    ##Xs = [hfls.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    ##Xs = [hfss.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    ##Xs = [zg300.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    

    ##Xs = [ua300.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)

    ##Xs = [va300.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    # ========= Use Previous times ===========

    ##Xs = [t2m.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau-4,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
        
    ##Xs = [zg500.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau-4,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    ##X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    
    ##Xs = [mrso.ReshapeInto2Dseries(time_start, time_end,lat_from1,lat_to1,lon_from1,lon_to1,T,tau-4,dim=2) for lat_from1,lat_to1, lon_from1, lon_to1 in zip(lat_from,lat_to,lon_from,lon_to)] # here we extract the portion of the globe
    #X= np.concatenate([X, np.concatenate(Xs, axis=2)[:,:,:,np.newaxis]], axis=3)
    # ========== Coarse Graining: ============
    #X1 = t2m.DownScale(time_start,time_end,lat_start,lat_end,lon_start,lon_end,T,tau, (18,42))
    #X2 = zg500.DownScale(time_start,time_end,lat_start,lat_end,lon_start,lon_end,T,tau, (18,42))
    #X3 = mrso.DownScale(time_start,time_end,lat_start,lat_end,lon_start,lon_end,T,tau, (18,42))
    #X = np.concatenate([X1[:,:,:,np.newaxis],  X2[:,:,:,np.newaxis],  X3[:,:,:,np.newaxis]], axis=3)

    # if we want to use FFT space (2D representation)
    ##X = t2m.ComputeFFT(time_start, time_end,T,tau,'real')
    ##X = t2m.ComputeFFThalf(time_start, time_end,T,tau,'real')
    ##X = zg500.ComputeFFThalf(time_start, time_end,T,tau,'real')
    ##X = zg500.ComputeFFT(time_start, time_end,T,tau,'real')
    
    #X = zg500.ComputeFFTnoPad(time_start, time_end,T,tau,'real',(18,42))
    del t2m.var
    gc.collect() # Garbage collector which removes some extra references to the object
    usepipelines = A_reshape, threshold, checkpoint_name_previous, tau
    undersampling_factor = [undersampling_factor, oversampling_factor]
                                
    return X, list_extremes, thefield, sampling, percent, usepipelines, undersampling_factor, new_mixing,  saveweightseveryblaepoch, NUM_EPOCHS, BATCH_SIZE, checkpoint_name, fullmetrics

if __name__ == '__main__':
    print("====== running Learn.py ====== ")  
    print("tf.__version__ = ",tf.__version__)
    if int(tf.__version__[0]) < 2:
        print("tf.test.is_gpu_available() = ", tf.test.is_gpu_available())
    else:
        print("tf.config.list_physical_devices('GPU') = ", tf.config.list_physical_devices('GPU'))

    start = time.time()



    X, list_extremes, thefield, sampling, percent, usepipelines, undersampling_factor, new_mixing,  saveweightseveryblaepoch, NUM_EPOCHS, BATCH_SIZE, checkpoint_name, fullmetrics = PrepareData()
    
    oversampling_factor = undersampling_factor[1]
    undersampling_factor = undersampling_factor[0]
                                
    print("full dimension of the data is X[0].shape = ", X[0].shape) # do the previous statement in steps so that first we get a list (I extract the necessary sizes)


    end = time.time()

    # Getting % usage of virtual_memory ( 3rd field)
    print('RAM memory used:', psutil.virtual_memory()[3])
    print("Reading time = ",end - start)
    start = time.time()


    mylabels = np.array(list_extremes)
    checkpoint_name_previous = usepipelines[2]
    tau = usepipelines[3]

    if tau < 0: # else tau = 0 is assumed to be the first training we perform

        # Here we insert analysis of the previous tau with the assessment of the ideal checkpoint
        history = np.load(checkpoint_name_previous+'/batch_'+str(0)+'_history.npy', allow_pickle=True).item()
        if ('val_CustomLoss' in history.keys()):
            print( "'val_CustomLoss' in history.keys()")
            historyCustom = []
            for i in range(10): # preemptively compute the optimal score
                historyCustom.append(np.load(checkpoint_name_previous+'/batch_'+str(i)+'_history.npy', allow_pickle=True).item()['val_CustomLoss'])
            historyCustom = np.mean(np.array(historyCustom),0)
            opt_checkpoint = np.argmin(historyCustom) # We will use optimal checkpoint in this case!
        else:
            print( "'val_CustomLoss' not in history.keys()")
            sys.exit("Aborting the program!")


    my_MCC = np.zeros(10,)
    my_entropy = np.zeros(10,)
    my_skill = np.zeros(10,)
    my_BS = np.zeros(10,)
    my_WBS = np.zeros(10,)
    my_freq = np.zeros(10,)
    my_memory = []

    for i in range(10):
        print("===============================")
        print("cross validation i = ", str(i))
        if isinstance(X, list):
            print("X is a list")
            test_indices, train_indices, train_true_labels_indices, train_false_labels_indices, filename_permutation = TrainTestSplitIndices(i,X[0], mylabels, 1, sampling, new_mixing, thefield, percent) # 1 implies undersampling_rate=1 indicating that we supress the manual undersampling
        else:
            print("X is not a list")
            test_indices, train_indices, train_true_labels_indices, train_false_labels_indices, filename_permutation = TrainTestSplitIndices(i,X, mylabels, 1, sampling, new_mixing, thefield, percent) # 1 implies undersampling_rate=1 indicating that we supress the manual undersampling
        print("# events in the train sample after TrainTestSp;litIndices: ",  len(train_indices))
        print("original proportion of positive events in the train sample: ",  np.sum(mylabels[train_indices])/len(train_indices))
        
        
        oversampling_strategy = oversampling_factor/(100/percent-1)
        if oversampling_factor > 1:
            print("oversampling_strategy = ", oversampling_strategy )
            over = RandomOverSampler(random_state=42, sampling_strategy=oversampling_strategy) # first oversample the minority class to have 15 percent the number of examples of the majority class
            #over = SMOTEENN(random_state=42, sampling_strategy=oversampling_strategy) # first oversample the minority class to have 15 percent the number of examples of the majority class
        
        undersampling_strategy = undersampling_factor*oversampling_strategy
        print("undersampling_strategy = ", undersampling_strategy )
        under = RandomUnderSampler(random_state=42, sampling_strategy=undersampling_strategy)
                            
        if oversampling_factor > 1:
                steps = [('o', over), ('u', under)]
        else:
                steps = [('u', under)]
        pipeline = Pipeline(steps=steps) # The Pipeline can then be applied to a dataset, performing each transformation in turn and returning a final dataset with the accumulation of the transform applied to it, in this case oversampling followed by undersampling.
        # To make use of the in-built pipelines we need to transform the X into the required dimensions
        if isinstance(X, list): # if list we are dealing with fused (combined) approach (at least partially)
            XTrain_indicesShape = [Xloop[train_indices].shape for Xloop in X] # each element of X has a specific shape
            XTrain_indicesLength = [reduce(mul, XTrain_indicesShapeIter[1:]) for XTrain_indicesShapeIter in XTrain_indicesShape] # each shape is converted to an integer
            XTrain_indicesLengthAccumulate = list(itertools.accumulate(XTrain_indicesLength))
            XTrain_indicesLengthAccumulate.insert(0,0)
            print("Original dimension of the train set is X[train_indices].shape = ", XTrain_indicesShape)
            print("Original dimension of the train set is XTrain_indicesLength = ", XTrain_indicesLength)
            print("Original dimension of the train set is XTrain_indicesLengthAccumulate = ", XTrain_indicesLengthAccumulate)
            X_train, Y_train = pipeline.fit_resample(np.concatenate([Xloop[train_indices].reshape(Train_indicesShapeloop[0], XTrain_indicesLengthloop) for Xloop, Train_indicesShapeloop, XTrain_indicesLengthloop in zip(X, XTrain_indicesShape, XTrain_indicesLength)], axis=1), mylabels[train_indices])
            print("post-pipeline X_train.shape = ", X_train.shape)
            # Next step is to unpack the X into its intended dimension
            for myiter in range(len(XTrain_indicesShape)): # number of samples has changed
                temp = list(XTrain_indicesShape[myiter])
                temp[0] = X_train.shape[0]
                XTrain_indicesShape[myiter] = tuple(temp)#.insert(0,X_train.shape[0]))
                 
            print("XTrain_indicesShape = ", XTrain_indicesShape)
            X_train = [X_train[:,XTrain_indicesLengthAccumulate1: XTrain_indicesLengthAccumulate2].reshape(XTrain_indicesShapeloop) for XTrain_indicesLengthAccumulate1, XTrain_indicesLengthAccumulate2, XTrain_indicesShapeloop in zip(XTrain_indicesLengthAccumulate[:-1],XTrain_indicesLengthAccumulate[1:],XTrain_indicesShape)] 
        else: # If X is not a list we expect it to be an array useful for fully stacked approach
            XTrain_indicesShape = X[train_indices].shape
            print("Original dimension of the train set is X[train_indices].shape = ", XTrain_indicesShape)
            #X_train, Y_train = pipeline.fit_resample(X[train_indices].reshape(XTrain_indicesShape[0],XTrain_indicesShape[1]*XTrain_indicesShape[2]*XTrain_indicesShape[3]),  mylabels[train_indices])
            #X_train = X_train.reshape(X_train.shape[0],XTrain_indicesShape[1],XTrain_indicesShape[2],XTrain_indicesShape[3])
            XTrain_indicesShape = list(XTrain_indicesShape)
            print("XTrain_indicesShape = ", XTrain_indicesShape)
            X_train, Y_train = pipeline.fit_resample(X[train_indices].reshape(tuple([XTrain_indicesShape[0],np.prod(XTrain_indicesShape[1:])])),  mylabels[train_indices])
            XTrain_indicesShape[0] = X_train.shape[0]
            print("XTrain_indicesShape = ", XTrain_indicesShape)
            X_train = X_train.reshape(tuple(XTrain_indicesShape))

        Y_test = mylabels[test_indices]
        neg = train_false_labels_indices.shape[0]
        pos = train_true_labels_indices.shape[0]
        
        if isinstance(X, list): # If list we need to renormalize it for each instance of the list
            for Xdim in range(len(X)):
                print("dimension of the train set is X[", Xdim, "][train_indices].shape = ", X[Xdim][train_indices].shape)
            print("# of the true labels = ", np.sum(mylabels[train_indices]))
            print("effective sampling rate for rare events is ", np.sum(mylabels[train_indices])/X[0][train_indices].shape[0])

            X_mean = [np.mean(Xloop[train_indices], 0) for Xloop in X]
            for X_meanloop in X_mean:
                print("X_meanloop.shape = ", X_meanloop.shape)
            X_std = [np.std(Xloop[train_indices],0) for Xloop in X]
            for X_stdloop in X_std:
                print("X_stdloop.shape = ", X_stdloop.shape)
                X_stdloop[X_stdloop==0] = 1 # If there is no variance we shouldn't divide by zero
             
            X_test = [] # Normalization applied here
            for iteration in range(len(X_std)):
                X_test.append( (X[iteration][test_indices]-X_mean[iteration])/X_std[iteration] )
                X_train[iteration] = (X_train[iteration]-X_mean[iteration])/X_std[iteration]
            print("====Dimensions of the data before entering the neural net===")
            print("unpacked normalized X_train.shape = ", [X_trainloop.shape for X_trainloop in X_train])
            print("X_test.shape = ", [X_testloop.shape for X_testloop in X_test])
        else: # If not a list we expect an array and thus much more straightforward normalization
            print("====Dimensions of the data before entering the neural net===")
            print("dimension of the train set is X[train_indices].shape = ", X_train.shape)
            X_mean = np.mean(X_train,0)
            X_std = np.std(X_train,0)
            X_std[X_std==0] = 1 # If there is no variance we shouldn't divide by zero

            X_test = (X[test_indices]-X_mean)/X_std
            Y_test = mylabels[test_indices]

            X_train = (X_train-X_mean)/X_std


         
        print("Y_train.shape = ", Y_train.shape)
        print("Y_test.shape = ", Y_test.shape)
         
        print("Train set: # of true labels = ", np.sum(Y_train), " ,# of false labels = ", Y_train.shape[0] - np.sum(Y_train))
        print("Train set: effective sampling rate for rare events is ", np.sum(Y_train)/Y_train.shape[0])
        
        np.save(checkpoint_name+'/batch_'+str(i)+'_X_mean', X_mean)
        np.save(checkpoint_name+'/batch_'+str(i)+'_X_std', X_std)

        if tau < 0:
            print("opt_checkpoint: ", opt_checkpoint, " ,loading model: ", checkpoint_name_previous)
            model = (tf.keras.models.load_model(checkpoint_name_previous+'/batch_'+str(i), compile=False)) # if we just want to train

            nb_zeros_c = 4-len(str(opt_checkpoint))
            cp_checkpoint_name = '/cp-'+nb_zeros_c*'0'+str(opt_checkpoint)+'.ckpt'
            print("loading weights from ",checkpoint_name_previous+'/batch_'+str(i)+cp_checkpoint_name)
            model.load_weights(checkpoint_name_previous+'/batch_'+str(i)+cp_checkpoint_name)
        else:

            if isinstance(X, list):
                inputs = []
                for myindex in range(len(X)): # preparing inputs for the probability softmax
                    model_input_dim = X[myindex].shape[1:]
                    inputs.append(layers.Input(shape=model_input_dim))
                print("inputs = ", inputs)
                x1 = CNN_layers(inputs[0])
                x2 = layers.Dense(8, activation='relu')(inputs[1])
                x = layers.Concatenate()([x1, x2])
                outputs = bottom_layers(x)
                model = keras.Model(inputs, outputs)
            else:
                model_input_dim = X.shape[1:] #(X.shape[1],X.shape[2])
                model = custom_CNN(model_input_dim) 
            """
            model_input_dim = X.shape[1:] #(X.shape[1],X.shape[2])
            model = create_regularized_model(1e-9, 1)
            
            print("model_input_dim = ",model_input_dim)
            """

        tf_sampling = tf.cast([0.5*np.log(undersampling_factor), -0.5*np.log(undersampling_factor)], tf.float32)
        model.summary()
        if fullmetrics:
            #METRICS=['accuracy',MCCMetric(2),ConfusionMatrixMetric(2)]   # the last two make the code run longer but give precise discrete prediction benchmarks
            METRICS=['accuracy',MCCMetric(2),ConfusionMatrixMetric(2),CustomLoss(tf_sampling)]#tf.keras.metrics.SparseCategoricalCrossentropy(from_logits=True)]#CustomLoss()]   # the last two make the code run longer but give precise discrete prediction benchmarks
        else:
            METRICS=['loss']
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate = 5e-5),
            #optimizer=tf.keras.optimizers.Adam(),
            loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), #If the predicted labels are not converted to a probability distribution by the last layer of the model (using sigmoid or softmax activation functions), we need to inform these three Cross-Entropy functions by setting their from_logits = True.
            #One advantage of using sparse categorical cross-entropy is it saves storage in memory as well as time in computation because it simply uses a single integer for a class, rather than a whole one-hot vector. This works despite the fact that the neural network has an one-hot vector output  
            metrics=METRICS   # the last two make the code run longer but give precise discrete prediction benchmarks
        )
        # Create a callback that saves the model's weights every saveweightseveryblaepoch epochs
        checkpoint_path = checkpoint_name+'/batch_'+str(i)+"/cp-{epoch:04d}.ckpt"
        if saveweightseveryblaepoch > 0:
            print("cp_callback save option on")
            # Create a callback that saves the model's weights
            cp_callback = tf.keras.callbacks.ModelCheckpoint(filepath=checkpoint_path,
                                                             save_weights_only=True,
                                                             verbose=1)
        else:
            cp_callback=None

        model.save_weights(checkpoint_path.format(epoch=0))

        if undersampling_factor < 1: # without pipelines batchsize and oversampling must be done within model.fit environment
            class_weight = {0: (undersampling_factor), 1: (1-undersampling_factor)}
        else:
            class_weight = None
        my_history=model.fit(X_train, Y_train, batch_size=BATCH_SIZE, validation_data=(X_test,Y_test), shuffle=True, callbacks=[cp_callback], epochs=NUM_EPOCHS,verbose=2, class_weight=class_weight)

        model.save(checkpoint_name+'/batch_'+str(i))
        np.save(checkpoint_name+'/batch_'+str(i)+'_history.npy',my_history.history)
        if isinstance(X, list):
            my_probability_model = probability_model(inputs,model)
        else:
            my_probability_model=(tf.keras.Sequential([ # softmax output to make a prediction
              model,
              tf.keras.layers.Softmax()
            ]))

        print("======================================")
        my_memory.append(psutil.virtual_memory())
        print('RAM memory:', my_memory[i][3])


        del X_test, Y_test
        tf.keras.backend.clear_session()
        gc.collect() # Garbage collector which removes some extra references to the object

        # Getting % usage of virtual_memory ( 3rd field)
    print(f" TOTAL MCC  = {np.mean(my_MCC):.3f} +- {np.std(my_MCC):.3f} , entropy = {np.mean(my_entropy):.3f} +- {np.std(my_entropy):.3f} , skill = {np.mean(my_skill):.3f} +- {np.std(my_skill):.3f}, Brier = {np.mean(my_BS):.3f} +- {np.std(my_BS):.3f} , Weighted Brier = {np.mean(my_WBS):.3f} +- {np.std(my_WBS):.3f} , frequency = {np.mean(my_freq):.3f} +- {np.std(my_freq):.3f}")

    np.save(checkpoint_name+'/RAM_stats.npy', my_memory)

    end = time.time()
    print("files saved in ", checkpoint_name)
    print("Learning time = ",end - start)



