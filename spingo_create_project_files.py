#!/usr/bin/env python

import subprocess
import sys, os,stat,glob
import csv
import time
import shutil
import datetime
import argparse
import pymysql as MySQLdb
today = str(datetime.date.today()) 
#import ConMySQL
ranks = ('domain','phylum','class','orderx','family','genus','species','strain')
domains = ('Archaea','Bacteria','Eukarya','Organelle','Unknown')

class FastaReader:
    def __init__(self,file_name=None):
        self.file_name = file_name
        self.h = open(self.file_name)
        self.seq = ''
        self.id = None

    def next(self): 
        def read_id():
            return self.h.readline().strip()[1:]

        def read_seq():
            ret = ''
            while True:
                line = self.h.readline()
                
                while len(line) and not len(line.strip()):
                    # found empty line(s)
                    line = self.h.readline()
                
                if not len(line):
                    # EOF
                    break
                
                if line.startswith('>'):
                    # found new defline: move back to the start
                    self.h.seek(-len(line), os.SEEK_CUR)
                    break
                    
                else:
                    ret += line.strip()
                    
            return ret
        
        self.id = read_id()
        self.seq = read_seq()
        
        if self.id:
            return True  
            
def run_taxonomy(args, ds, ds_count, files):
    print('tax')
    project_dataset = args.project+'--'+ds
    taxa_lookup = {}
    read_id_lookup={}
    with open(files['gast_file'],'r') as f:
        next(f)  # skip header
        for line in f:
        
            line = line.strip()
            items = line.split("\t")
            if args.verbose:
                print(items)
            taxa = items[1]
            if taxa[-3:] == ';NA':
                taxa = taxa[:-3]
            #read_id=items[0]  # this is the whole id from mothur -> won't match the clean id 
            if args.datasetname_not_in_unique_file:
                read_id = items[0].split()[0]  #M00270:130:000000000-A8DLT:1:1101:21493:2094;barcodelabel=oranje-touw-zeeb1-2_S79|frequency:2174
                freq_from_defline = items[0].split(':')[-1]
            else:
                #read_id = items[0].split()[1]  #10445.7p2_22437835 IIU3AEM07H62IP orig_bc=ACGAGTGCGT new_bc=ACGAGTGCGT bc_diffs=0|frequency:1
                #freq_from_defline = items[0].split()[-1].split(':')[1]
                
                read_id = items[0].split('|')[1]
                freq_from_defline = items[0].split('|')[-1].split(':')[1]
            if args.verbose:
                print('id=',read_id)
                print('  freq=',freq_from_defline)
            read_id_lookup[read_id] = taxa
        
            # the count here is the frequency of the taxon in the datasets
            
            if taxa in taxa_lookup:                
                try:
                    taxa_lookup[taxa] += int(freq_from_defline)
                except:
                    taxa_lookup[taxa] += 1
            else:
                try:
                    taxa_lookup[taxa] = int(freq_from_defline)
                except:
                    taxa_lookup[taxa] = 1
        
    ###############################
    #  DATA CUBE TABLE
    # taxa_lookup: {'Unknown': 146, 'Bacteria': 11888, 'Bacteria;Chloroflexi': 101}
    # dataset_count is 3 (3 taxa in this dataset)
    # frequency is 3/144
    print('Running data_cube')
    fh1 = open(files['taxes_file'],'w')

    fh1.write("\t".join( ["HEADER","project", "dataset", "taxonomy", "superkingdom", 
                        "phylum", "class", "orderx", "family", "genus", "species", 
                        "strain", "rank", "knt", "frequency", "dataset_count", "classifier"]) + "\n")
    tax_collector={}
    summer=0
    for tax,knt in taxa_lookup.iteritems():
        if args.verbose:
            print(tax,knt)
        summer += knt
        datarow = ['',args.project,ds]
    
        taxa = tax.split(';')
        #if taxa[0] in C.domains:
        freq = float(knt) / int(ds_count)
        rank = ranks[len(taxa)-1]
        for i in range(len(ranks)):                
            if len(taxa) <= i:
                if ranks[i] == 'orderx':
                    taxa.append("order_NA")
                else:
                    taxa.append(ranks[i] + "_NA")

        tax_collector[tax] = {}


        datarow.append(tax)
        datarow.append("\t".join(taxa))
        datarow.append(rank)
        datarow.append(str(knt))
        datarow.append(str(freq))
        datarow.append(str(ds_count))
        datarow.append('GAST')
    
        w = "\t".join(datarow)
       
        fh1.write(w+"\n")
   
        tax_collector[tax]['rank'] = rank
        tax_collector[tax]['knt'] = knt
        tax_collector[tax]['freq'] = freq
        
    fh1.close()
    
    ########################################
    #
    # SUMMED DATA CUBE TABLE
    #
    ########################################
    print('Running summed_(junk)_data_cube')
    fh2 = open(files['summed_taxes_file'],'w')
    
    fh2.write("\t".join(["HEADER","taxonomy", "sum_tax_counts", "frequency", "dataset_count","rank", 
                        "project","dataset","project--dataset","classifier"] )+"\n")
    ranks_subarray = []
    rank_list_lookup = {}
    for i in range(0, len(ranks)): 
        ranks_subarray.append(ranks[i])
        ranks_list = ";".join(ranks_subarray) # i.e., superkingdom, phylum, class
        # open data_cube file again
        # taxes_file: data_cube_uploads
        for line in  open(files['taxes_file'],'r'):
            line = line.strip().split("\t")
            knt = line[12]
            taxon = line[2]
            if line[0] == 'HEADER':
                continue
            if taxon in tax_collector:
                knt = tax_collector[taxon]['knt']
            else:
                print('ERROR tax not found in tax_collector: assigning zero')
                knt = 0
            idx = len(ranks_subarray)
            l=[]
            for k in range(3,idx+3):                    
                l.append(line[k])
            tax = ';'.join(l)
                       
            
            if tax in rank_list_lookup:
                rank_list_lookup[tax] += knt
            else:
                rank_list_lookup[tax] = knt
                
            
      
    for tax,knt in rank_list_lookup.iteritems():
        
        
        taxa = tax.split(';')
        #if taxa[0] in C.domains:
        rank = len( taxa ) -1
        
        frequency = float(knt) / int(ds_count)
        
        if len(tax) - len(''.join(taxa)) >= rank:
        
            datarow = ['']
            datarow.append(tax)
            datarow.append(str(knt))
            datarow.append(str(frequency))
            datarow.append(str(ds_count))
            datarow.append(str(rank))
            datarow.append(args.project)
            datarow.append(ds)
            datarow.append(project_dataset)
            datarow.append('GAST')
        
            w = "\t".join(datarow)
            
            fh2.write(w+"\n")
            

    fh2.close()
    
    
    ####################################       
    #
    # DISTINCT TAXONOMY
    #
    ####################################
    print('Running taxonomy')
    fh3 = open(files['distinct_taxes_file'],'w')
    fh3.write("\t".join(["HEADER","taxon_string", "rank", "num_kids"] )+"\n")
    taxon_string_lookup={}
    for line in  open(files['summed_taxes_file'],'r'):
        if line.split("\t")[0] == 'HEADER':
            continue
        items = line.strip().split("\t")            
        taxon_string = items[0]
        
        if taxon_string in taxon_string_lookup:
            taxon_string_lookup[taxon_string] += 1
        else:
            taxon_string_lookup[taxon_string] = 1
    
    for taxon_string,v in taxon_string_lookup.iteritems():
        datarow = ['']
        datarow.append(taxon_string)
        taxa = taxon_string.split(';')
        if taxa[0] in domains:
            rank = str(len(taxa)-1)
            datarow.append(rank)
            if rank==7 or taxon_string[-3:]=='_NA':
                num_kids = '0'
            else:
                num_kids = '1'
            datarow.append(num_kids)
            w = "\t".join(datarow)
           
            fh3.write(w+"\n")
    fh3.close()
    
    return (tax_collector,read_id_lookup)
    
def run_sequences(args, ds, tax_collector, read_id_lookup, files):
    print('Running sequences')
    refid_collector={}
    project_dataset = args.project+'--'+ds
    with open(files['gast_file'],'r') as f:
        next(f)  # skip header
        for line in f:
            line = line.strip()
        
            items=line.split("\t")
            if args.verbose:
                print(items)
            if args.datasetname_not_in_unique_file:
                id = items[0]
            else:
                id = items[1]
            distance = items[2]
            refhvr_ids = items[-1] # always last? separated by ,,
            if args.verbose:
                print('refhvr_ids',refhvr_ids)
            refid_collector[id] = {}
            refid_collector[id]['distance'] = distance
            refid_collector[id]['refhvr_ids'] = refhvr_ids
    fh = open(files['sequences_file'],'w')
    fh.write("\t".join(["HEADER","sequence","project","dataset","taxonomy","refhvr_ids", "rank",
                            "seq_count","frequency","distance","read_id","project_dataset"] )+"\n")
        
           
    # open uniques fa file
    f = FastaReader(files['unique_file'])
    while f.next():
        datarow = ['']
        (cnt, true_id) = run_defline(args, f.id)
               
        
        if args.verbose:
            print('cnt from uniques file',cnt)
        seq = f.seq.upper()
        if true_id in read_id_lookup:
            if args.verbose:
                print('FOUND TAX for sequences file')
            tax = read_id_lookup[true_id]
        else: 
            print('ERROR:: NO TAX for sequences file')
            sys.exit()
            tax = ''
            
        if tax in tax_collector:
            rank = tax_collector[tax]['rank']
            #cnt = tax_collector[tax]['knt']
            freq = tax_collector[tax]['freq']
        else:
            rank = 'NA'
            cnt  = 0
            freq = 0
            
        if id in refid_collector:
            distance = refid_collector[id]['distance']
            refhvr_ids = refid_collector[id]['refhvr_ids']
        else:
            distance = '1.0'
            refhvr_ids = '0'
        if not cnt:
            cnt = 1
        datarow.append(seq)
        datarow.append(args.project)
        datarow.append(ds)
        datarow.append(tax)
        datarow.append(refhvr_ids)
        datarow.append(rank)
        datarow.append(str(cnt))
        datarow.append(str(freq))
        datarow.append(distance)
        datarow.append(true_id)
        datarow.append(project_dataset)
        w = "\t".join(datarow)
        
        fh.write(w+"\n")
    fh.close()
    return refid_collector      
    
            
def run_projects(args, ds, ds_count, files):
    print('Running projects')
    project_dataset = args.project+'--'+ds
    date_trimmed = 'unknown'
    dataset_description = ds
    has_tax = '1' # true
    fh = open(files['projects_datasets_file'],'w')
    
    fh.write("\t".join(["HEADER","project","dataset","dataset_count","has_tax", "date_trimmed","dataset_info"] )+"\n")
    fh.write("\t"+"\t".join([args.project, ds, str(ds_count), has_tax, date_trimmed, dataset_description] )+"\n")
    
    fh.close()
    
def run_defline(args, defline):
    # EDIT/EDIT/EDIT to match defline splitter
    defline_splitter = '|'
    parts = defline.split(defline_splitter)
    # for MoBE:  ['10445.7p2_22423662', 'IIU3AEM07H2G36', 'orig_bc=ACGAGTGCGT', 'new_bc=ACGAGTGCGT', 'bc_diffs=0|frequency:1']
    print(parts)
    if args.datasetname_not_in_unique_file:
        true_id = parts[0]
    else:
        true_id = parts[1]
    try:
        cnt = parts[-1].split(':')[1]
        counts_are_from_uniques_file = True
    except:
        cnt = 1
        counts_are_from_uniques_file = False
    print('cnt',cnt)
    return (cnt, true_id)
    
def run_info(args, ds, files, project_count):
    print('Running info')
    
    #try:
    # get 'real' data from database
    db = get_db_connection(args)
    cursor = db.cursor()
    print('Connecting to '+args.site+' database, to get user "'+args.user+'" information')
    query = "SELECT last_name,first_name,email,institution from vamps_auth where user='%s'" % (args.user)
    print(query)
    
    cursor.execute(query)
    data = cursor.fetchone()
    contact= data[1]+' '+data[0]
    email= data[2]
    institution= data[3]
    
    
    fh = open(files['project_info_file'],'w')
    title="title"
    description='description'
    
    
    fh.write("\t".join(["HEADER","project","title","description","contact", "email","institution","user","env_source_id","edits","upload_date","upload_function","has_tax","seq_count","project_source","public"] )+"\n")
    fh.write("\t"+"\t".join([args.project, title, description, contact, email, institution, args.user, args.env_source_id, args.user, today, 'script', '1', str(project_count), 'script', '0'] )+"\n")
    # if this project already exists in the db???
    # the next step should update the table rather than add new to the db
    
    fh.close()
    

def get_db_connection(args):
    print(args)
    db = MySQLdb.connect( host=args.site, db=args.database,
             read_default_file="~/.my.cnf" # you can use another ini file, for example .my.cnf
           )
    cur = db.cursor()

    return db

def create_vamps_files(args, ds, ds_count, project_count):
    """
    Creates the vamps files in the gast directory ready for loading into vampsdb
    """
    files = gather_files_per_ds(args, ds)
    if not ds_count:
        print("no ds count fount -- looking in fasta file for frequency")
        ds_count = get_ds_count_from_defline(files['unique_file'])
         
         
    (tax_collector, read_id_lookup) = run_taxonomy(args, ds, ds_count, files)
    refid_collector = run_sequences(args, ds, tax_collector, read_id_lookup, files)   
    run_projects(args, ds, ds_count, files)
    run_info(args, ds, files, project_count)
        
      
    return files
    
def get_ds_count_from_defline(file):
    f = FastaReader(file)
    ds_count = 0
    while f.next():
        datarow = ['']
        (cnt, true_id) = run_defline(args, f.id)
        ds_count += int(cnt)
    return ds_count      
def gather_files_per_ds(args, ds):
    
    files={}
    if args.datasetnames_in_mbl_metadata_file:
        
        prefix = args.mdobj[ds]['prefix']
        files['unique_file'] = os.path.join('./', prefix+args.fasta_file_suffix)
        files['gast_file']   = os.path.join(args.indir, prefix+args.gast_file_suffix)
    else:
        files['gast_file']                 = os.path.join(args.indir,ds+'.'+args.file_suffix_part1+'.unique.gast')
        files['unique_file']               = os.path.join('./',ds+'.'+args.file_suffix_part1+'.unique')
        files['names_file']                = os.path.join('./',ds+'.'+args.file_suffix_part1+'.names')
        
    # to be created:
    files['taxes_file']                = os.path.join(args.outdir,ds,'vamps_data_cube_uploads.txt')
    files['summed_taxes_file']         = os.path.join(args.outdir,ds,'vamps_junk_data_cube_pipe.txt')
    files['distinct_taxes_file']       = os.path.join(args.outdir,ds,'vamps_taxonomy_pipe.txt')
    files['sequences_file']            = os.path.join(args.outdir,ds,'vamps_sequences_pipe.txt')
    files['projects_datasets_file']    = os.path.join(args.outdir,ds,'vamps_projects_datasets_pipe.txt')
    files['project_info_file']         = os.path.join(args.outdir,ds,'vamps_upload_info.txt')
    
    return files


    
def get_mbl_datasets(args):
    
    ds_list = {}
    project_count = 0
    
    mdobj_by_dataset = {}
    
    with open(args.md_file) as f: 
        lineno = 0
        for line in f: 
            line = line.strip().split(',')
            if lineno == 0:
                header = line
                                                
            else:
               file_prefix = line[args.barcode_index]+'_'+line[args.illumina_index_index]
               fasta_file = os.path.join('./',file_prefix+args.fasta_file_suffix)
               
               ds = line[args.dataset_name_index]
               # open uniques fa file
        
        
        
               ds_list[ds] = 0
               mdobj_by_dataset[ds] = {}
               for i,val in enumerate(line):
                   key = header[i]
                   mdobj_by_dataset[ds][key] = val               
               mdobj_by_dataset[ds]['prefix'] = file_prefix        
            lineno += 1
   
    
    return (ds_list, 0, mdobj_by_dataset)    

def start_vamps_file_creation(args, ds_list, project_count):
    
    # Question for anna about counts: the names file will have just one entry (2 columns) IF the
    # original seqs file was already uniqued BUT there will be a 'frequency:X' tagged on the end of the defline
    # so two ways to get counts: 1-from frequency:X tag ( may not be present)
    # OR 2-Count columns in names file
    # Answer check defline: if frequency:X is present use it -- if not: use names file
    file_collector={}
    args.outdir = create_out_dir(args, ds_list)
    for i,ds in enumerate(ds_list):
        print()
        if ds_list[ds] >= int(args.min_ds_count) or args.datasetnames_in_mbl_metadata_file:
            print('CreatingFiles',args.project,ds,i,'/',len(ds_list))
            
            check_for_infiles(args, ds)
            ds_cnt = ds_list[ds]
            file_collector[ds] = create_vamps_files(args, ds, ds_cnt, project_count)
        else:
            print('Skipping',ds,'count is less than',args.min_ds_count)
    
    return file_collector
    
def check_for_infiles(args,ds):
    if args.datasetnames_in_mbl_metadata_file:
        
        
        prefix = args.mdobj[ds]['prefix']
        unique= os.path.join('./', prefix+args.fasta_file_suffix)
        gast  = os.path.join(args.indir, prefix+args.gast_file_suffix)
    
        # grab csv file:                10445.7p2.fa.unique.gast
        # grab sequences file:          10445.7p2.fa.unique
        # grab names file for counts:   10445.7p2.fa.names
       
        if not os.path.isfile(gast):
            sys.exit( 'no gast file found--exiting: '+gast)
        if not os.path.isfile(unique):
            sys.exit( 'no unique file found--exiting: '+unique)
        print('all files found for '+ds+'*')
    else:
        names = os.path.join('./', ds+'.'+args.file_suffix_part1+'.names')
        unique= os.path.join('./', ds+'.'+args.file_suffix_part1+'.unique')
        gast  = os.path.join(args.indir, ds+'.'+args.file_suffix_part1+'.unique.gast')

        # grab csv file:                10445.7p2.fa.unique.gast
        # grab sequences file:          10445.7p2.fa.unique
        # grab names file for counts:   10445.7p2.fa.names
        if not os.path.isfile(names):
            sys.exit( 'no names file found--exiting: '+names)
        if not os.path.isfile(gast):
            sys.exit( 'no gast file found--exiting: '+gast)
        if not os.path.isfile(unique):
            sys.exit( 'no unique file found--exiting: '+unique)
        print('all files found for '+ds+'*')
    

    
def create_out_dir(args, ds_list):
    outdir = os.path.join(args.outdir_base,args.project)
    if os.path.exists(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)
    for ds in ds_list:
        if ds_list[ds] >= int(args.min_ds_count) or args.datasetnames_in_mbl_metadata_file:
            os.makedirs(os.path.join(outdir,ds))
    return outdir
#########################################################################################   
def get_datasets(args):
    
    ds_list = {}
    project_count = 0
    # EDIT/EDIT/EDIT to match unique files in current dir
    file_glob = os.path.join(args.indir,"*."+args.infile_suffix)
    #print('file_glob '+file_glob)
    files = glob.glob(file_glob)
    #files = glob.glob(os.path.join('./',"*.nonchimeric.fa"))
    # GGCTAC_NNNNTGACT_1_MERGED-MAX-MISMATCH-3.unique.nonchimeric.fa
    for file in files:
        #print(file)
        ds_count = 0
        base = os.path.basename(file)
        #ds = base[:-10]
        ds = base[:-len(args.infile_suffix)-1]
        print(ds)
        if args.verbose:
            print('ds',ds)
        with open(file,'r') as fp:
            for line in fp:
                items = line.strip().split('\t')
                # all these should have a frequency:X at the end
                cnt = items[0].split('|')[-1].split(':')[1]
                ds_count += int(cnt)
        project_count += int(ds_count)
        ds_list[ds]=ds_count
    
    return (ds_list, project_count)
    
def create_dataset_file(args):
    out_file_name = 'dataset_'+args.project+'.csv'
    out_file_path = os.path.join('./', out_file_name)
    
    with open(out_file_path,'w') as fp:
        print('Writing',out_file_name)
        fp.write('"dataset","dataset_description","env_sample_source_id","project"\n')
        for ds in args.ds_list:
            fp.write('"'+ds+'","'+ds+'","'+args.env_source_id+'","'+args.project+'"\n')
            
def create_project_file(args):
    out_file_name = 'project_'+args.project+'.csv'
    out_file_path = os.path.join('./', out_file_name)
    
    with open(out_file_path,'w') as fp:
        print('Writing',out_file_name)
        fp.write('"project","title","project_description","funding","env_sample_source_id","contact","email","institution"\n')
        fp.write('"'+args.project+'","'+args.title+'","'+args.description+'","","'+args.env_source_id+'","'+args.contact+'","'+args.email+'","'+args.institution+'"\n')    

def create_user_file(args):
    out_file_name = 'user_contact_'+args.project+'.csv'
    out_file_path = os.path.join('./', out_file_name)
    
    with open(out_file_path,'w') as fp:
        print('Writing',out_file_name)
        fp.write('"contact","username","email","institution","first_name","last_name","active","security_level","encrypted_password"\n')
        fp.write('"'+args.contact+'","'+args.user+'","'+args.email+'","","'+args.contact.split()[0]+'","'+args.contact.split()[1]+'","1","50","XXXXXXXXXXX"\n')    

def create_metadata_file(args):
    out_file_name = 'metadata_'+args.project+'.csv'
    out_file_path = os.path.join('./', out_file_name)             
    with open(out_file_path,'w') as fp:
        print('Writing empty',out_file_name)

                
def create_sequences_file(args):
    out_file_name = 'sequences_'+args.project+'.csv'
    out_file_path = os.path.join('./', out_file_name)
    file_glob = os.path.join(args.indir,"*."+args.infile_suffix)
    files = glob.glob(file_glob)
    
    with open(out_file_path,'w') as fp1:
        print('Writing',out_file_name)
        fp1.write('"id","sequence","project","dataset","taxonomy","refhvr_ids","rank","seq_count","frequency","distance","rep_id","project_dataset"\n') 
        for spingo_file in files:
            base = os.path.basename(spingo_file)
            ds = base[:-len(args.infile_suffix)-1]
            seqs_file = ds + '.fa.unique'  # need sequences
            seqs_by_id = {}  
            f = FastaReader(seqs_file)
            while f.next():
                seqs_by_id[f.id] = f.seq
            
            counter = 1
            with open(spingo_file,'r') as fp2:
                for line in fp2:
                    items = line.strip().split('\t')
                    id = items[0]
                    cnt = items[0].split('|')[-1].split(':')[1]
                    freq = float(cnt) / float(args.ds_list[ds])
                    tax = items[4]
                    seq = seqs_by_id[id] 
                    
                    rank = 'species'
                    if tax == 'AMBIGUOUS':
                        tax = 'Unknown' 
                        rank = 'NA'
                    fp1.write('"'+str(counter)+'","'+seq+'","'+args.project+'","'+ds+'","'+tax+'","0","'+rank+'","'+cnt+'","'+str(freq)+'","","",""\n')
                    
                    counter += 1
                
                
if __name__ == '__main__':
    
    
    # DEFAULTS
    site = 'vampsdev'
    
    

    data_object = {}
    

    
    myusage = """usage: spingo_create_project_file.py  [options]
         
         Pipeline: /groups/vampsweb/new_vamps_maintenance_scripts/*         
            Plan to create infiles for NEW VAMPS
            that mimic the files created by export_project.sh
         
         where
            
            Current dir contains the *names and *unique files
            While the gast files are in the ./gast directory
            
            -s/--site     vamps or [vampsdev]        
            
            -i/--indir    Default: 'SPINGO' in current dir     
            
            -p/--project  project name: REQUIRED     
            
            
            -o/--outdir   Where vamps files will be created: defaults to [project-name] which will be created. 
            
            
            
            Others to consider:
            -user
            
            -env_source
            
            -v/--v verbose
            
    
    
    """
    parser = argparse.ArgumentParser(description="" ,usage=myusage)                 
    
   
                                                     
    parser.add_argument("-s", "--site",          required=False,  action="store",   dest = "site", default='vampsdev',
                                                        help="""database hostname: vamps or vampsdev  [default: vampsdev]""")    
    parser.add_argument("-i",   "--indir", required=False,  action="store",   dest = "indir", default='./SPINGO',   help="Where datasets dirs are")       
    parser.add_argument("-p", "--project",    required=True,  action='store', dest = "project",  help="")   
    parser.add_argument("-o",     "--outdir",     required=False,  action='store', dest = "outdir_base",  default='./',help="")  
    parser.add_argument("-min",     "--min_ds_count",     required=False,  action='store', dest = "min_ds_count",  default='10',help="")                                        
    # others
    parser.add_argument("-v","--v",  required=False,  action="store_true",   dest = "verbose", default=False)  
    
    parser.add_argument("-u",        "--user",     required=False,  action="store",   dest = "user", default='admin')  
    # '100' is unknown                                   
    parser.add_argument("-env",      "--env_source_id",  required=False,  action="store",   dest = "env_source_id", default='100')  
    
    parser.add_argument("-fs",      "--file_suffix",  required=False,  action="store",   dest = "infile_suffix", default='fa.unique.spingo.out',
                                help='Part of the unique file name before the word unique' )                                                                                                                                                           
    
    args = parser.parse_args()
    # DEFAULTS
    #args.infile_suffix = 'fa.unique.spingo.out'
    #args.env_source_id = '100'   # unknown
    args.title = 'mytitle'
    args.description ='mydescription'
    args.contact = 'Ad Min'
    args.email = 'vamps@mbl.edu'
    args.institution = 'MBL'
    args.default_req_metadata = {
        "env_biome":"unknown",
        "env_feature":"unknown",
        "env_material":"unknown",
        "env_package":"unknown",
        "collection_date":"",
        "latitude":"",
        "longitude":"",
        "target_gene":"unknown",
        "dna_region":"unknown",
        "sequencing_platform":"unknown",
        "domain":"unknown",
        "geo_loc_name":"unknown",
        "adapter_sequence":"unknown",
        "illumina_index":"unknown",
        "primer_suite":"unknown",
        "run":"unknown"
    }
    
    if args.site == 'vamps':
        args.site = 'vampsdb'
    elif args.site == 'vampsdev':
        args.site = 'bpcweb7'
    args.database = 'vamps'
    file_collector = {}
    
    (args.ds_list, args.project_count) = get_datasets(args)
    print('ds_list')
    print(args.ds_list)
    
    
    
    ans = raw_input("Do you want to continue? (type 'Y' to continue): ")
    if ans.upper() != 'Y':
        sys.exit()
    if not args.ds_list:
        print('No datasets found! Its likely the  args.infile_suffix is set wrong')
        print('Here it is: "'+ args.infile_suffix+'"; Enter "-fp <new_pt>" to change')
        sys.exit()
    create_dataset_file(args)
    create_project_file(args)
    create_user_file(args)
    create_metadata_file(args)
    create_sequences_file(args)
    sys.exit()
    file_collector = start_vamps_file_creation(args, args.ds_list, args.project_count)
    
    