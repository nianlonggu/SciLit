import os
import shutil
from glob import glob
import argparse

ROOT_DATA_PATH = os.getenv("ROOT_DATA_PATH")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-tar_gz_folder", default =  ROOT_DATA_PATH + "/raw/tar_gz" )
    parser.add_argument("-save_folder", default =  ROOT_DATA_PATH + "/raw/xml" )
    
    args = parser.parse_args()
        
    if os.path.exists(args.save_folder):
        shutil.rmtree(args.save_folder)
    os.makedirs(args.save_folder)
        
    tar_files = glob( "%s/*.tar.gz"%( args.tar_gz_folder ) )
    
    print("unzip %d tar.gz files to folder %s ..."%(len(tar_files), args.save_folder  ))
    
    for tar_name in tar_files:
        os.system( "tar -xzvf %s -C %s/" %( tar_name, args.save_folder ) )
        
    