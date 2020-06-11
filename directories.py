'''
Central settings for save/load directories.
Note that not all modules may honour these settings.
'''

import os
import platform

CODE_ROOTDIR = os.path.dirname(os.path.realpath(__file__))

if platform.system() == 'Linux':
    # Where for example
    home = os.getenv("HOME")
    ANALYSES_SAVEDIR = home+'/analyses/pupil'

    # Where any temporal stuff as disk cahcing would go
    PROCESSING_TEMPDIR = home+'/analyses/pupil/tmp'

    # If lots of storage is needed
    PROCESSING_TEMPDIR_BIGFILES = home+'/pupil/tmp'

    # Where folders DrosoX_i, DrosoM_i are
    DROSO_DATADIR = home+'/smallbrains-nas1/array1/pseudopupil_joni'
    
    DROSO_DATADIRS = [home+'/smallbrains-nas1/array1/pseudopupil_imaging',
            DROSO_DATADIR]


elif platform.system() == 'Windows':
    root_dir = CODE_ROOTDIR
    DROSO_DATADIR = os.path.join(root_dir, '../DATA')
    ANALYSES_SAVEDIR = os.path.join(root_dir, '../RESULTS')
    PROCESSING_TEMPDIR = os.path.join(ANALYSES_SAVEDIR, 'tmp')
    PROCESSING_TEMPDIR_BIGFILES = PROCESSING_TEMPDIR

else:
    raise OSError('Unkown platform (not Windows or Linux)')

# Just another way to access these directories
ALLDIRS= {'ANALYSES_SAVEDIR': ANALYSES_SAVEDIR,
        'PROCESSING_TEMPDIR': PROCESSING_TEMPDIR,
        'PROCESSING_TEMPDIR_BIGFILES': PROCESSING_TEMPDIR_BIGFILES,
        'DROSO_DATADIR': DROSO_DATADIR}



def printDirectories():


    print('These are the directories')
    
    for key, item in ALLDIRS.items():
        print('{} {}'.format(key, item))


def directoriesExist():
    '''
    Check if directories exist, if not, create them.
    
    Currently when this module gets imported, this function runs.
    '''
    
    for key, item in ALLDIRS.items():

        if not os.path.exists(item):
            print('Folder {} for {} did not exist. Attempting to create it.'.format(item, key))
            os.makedirs(item)

if __name__ == "__main__":
    printDirectories()

directoriesExist()


