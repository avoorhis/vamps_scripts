#!/usr/bin/env python

""" 
  create_counts_lookup.py


"""

import sys, os, io
import argparse

try:
    import pymysql as MySQLdb
except ImportError:
    import MySQLdb
except:
    raise

import json
import shutil
import datetime
import socket

today = str(datetime.date.today())

"""
silva119 MISSING from taxcount(silva119 only) or json(silva119 or rdp2.6) files:
ID: 416 project: DCO_ORC_Av6

rdp
ID: 284 project: KCK_NADW_Bv6
ID: 185 project: LAZ_DET_Bv3v4
ID: 385 project: LAZ_PPP_Bv3v5
ID: 278 project: LAZ_SEA_Bv6v4
ID: 213 project: LTR_PAL_Av6

SELECT sum(seq_count), dataset_id, domain_id, domain
FROM sequence_pdr_info
JOIN sequence_uniq_info USING(sequence_id)
JOIN silva_taxonomy_info_per_seq USING(silva_taxonomy_info_per_seq_id)
JOIN silva_taxonomy USING(silva_taxonomy_id)
JOIN domain USING(domain_id)
JOIN phylum USING(phylum_id)
where dataset_id = '426'
GROUP BY dataset_id, domain_id

SELECT sum(seq_count), dataset_id, domain_id, domain, phylum_id, phylum
FROM sequence_pdr_info
JOIN sequence_uniq_info USING(sequence_id)
JOIN silva_taxonomy_info_per_seq USING(silva_taxonomy_info_per_seq_id)
JOIN silva_taxonomy USING(silva_taxonomy_id)
JOIN domain USING(domain_id)
JOIN phylum USING(phylum_id)
where dataset_id = '426'
GROUP BY dataset_id, domain_id, phylum_id
"""

query_coreA = " FROM sequence_pdr_info"
# query_coreA += " JOIN sequence_uniq_info USING(sequence_id)"

query_core_join_silva119 = " JOIN silva_taxonomy_info_per_seq USING(sequence_id)"
query_core_join_silva119 += " JOIN silva_taxonomy USING(silva_taxonomy_id)"
query_core_join_rdp = " JOIN rdp_taxonomy_info_per_seq USING(rdp_taxonomy_info_per_seq_id)"
query_core_join_rdp += " JOIN rdp_taxonomy USING(rdp_taxonomy_id)"

domain_queryA = "SELECT sum(seq_count), dataset_id, domain_id"

domain_queryB = " WHERE dataset_id in ('%s')"
domain_queryB += " GROUP BY dataset_id, domain_id"

phylum_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id"
phylum_queryB = " WHERE dataset_id in ('%s')"
phylum_queryB += " GROUP BY dataset_id, domain_id, phylum_id"

class_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id"
class_queryB = " WHERE dataset_id in ('%s')"
class_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id"

order_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id, order_id"
order_queryB = " WHERE dataset_id in ('%s')"
order_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id, order_id"

family_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id, order_id, family_id"
family_queryB = " WHERE dataset_id in ('%s')"
family_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id, order_id, family_id"

genus_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id"
genus_queryB = " WHERE dataset_id in ('%s')"
genus_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id"

species_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id, species_id"
species_queryB = " WHERE dataset_id in ('%s')"
species_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id, species_id"

strain_queryA = "SELECT sum(seq_count), dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id, species_id, strain_id"
strain_queryB = " WHERE dataset_id in ('%s')"
strain_queryB += " GROUP BY dataset_id, domain_id, phylum_id, klass_id, order_id, family_id, genus_id, species_id, strain_id"

cust_pquery = "SELECT project_id, field_name from custom_metadata_fields WHERE project_id = '%s'"

queries = [{"rank": "domain", "queryA": domain_queryA, "queryB": domain_queryB},
           {"rank": "phylum", "queryA": phylum_queryA, "queryB": phylum_queryB},
           {"rank": "klass", "queryA": class_queryA, "queryB": class_queryB},
           {"rank": "order", "queryA": order_queryA, "queryB": order_queryB},
           {"rank": "family", "queryA": family_queryA, "queryB": family_queryB},
           {"rank": "genus", "queryA": genus_queryA, "queryB": genus_queryB},
           {"rank": "species", "queryA": species_queryA, "queryB": species_queryB},
           {"rank": "strain", "queryA": strain_queryA, "queryB": strain_queryB}
           ]


def convert_keys_to_string(dictionary):
    """Recursively converts dictionary keys to strings."""
    if not isinstance(dictionary, dict):
        return dictionary
    return dict((str(k), convert_keys_to_string(v)) for k, v in dictionary.items())


def get_dco_pids():
    query = "select project_id from project where project like 'DCO%'"
    cur.execute(query)
    rows = cur.fetchall()
    pid_list = []
    for row in rows:
        pid_list.append(str(row[0]))

    return ', '.join(pid_list)


def go_add(NODE_DATABASE, pids_str):
    from random import randrange
    counts_lookup = {}
    prefix = ""
    if args.units == 'silva119':
        prefix = os.path.join(args.json_file_path, NODE_DATABASE + '--datasets_silva119')
    elif args.units == 'rdp2.6':
        prefix = os.path.join(args.json_file_path, NODE_DATABASE + '--datasets_rdp2.6')

    if not os.path.exists(prefix):
        os.makedirs(prefix)
    print prefix
    all_dids = []
    metadata_lookup = {}

    pid_list = pids_str.split(', ')
    # Uniquing list here
    pid_set = set(pid_list)
    pid_list = list(pid_set)
    for k, pid in enumerate(pid_list):
        dids = get_dataset_ids(pid)
        all_dids += dids
        # delete old did files if any
        for did in dids:
            pth = os.path.join(prefix, did + '.json')
            try:
                os.remove(pth)
            except:
                pass
        did_sql = "', '".join(dids)
        # print counts_lookup
        for q in queries:
            if args.units == 'rdp2.6':
                query = q["queryA"] + query_coreA + query_core_join_rdp + q["queryB"] % (did_sql)
            elif args.units == 'silva119':
                query = q["queryA"] + query_coreA + query_core_join_silva119 + q["queryB"] % (did_sql)
            print 'PID =', pid, '(' + str(k + 1), 'of', str(len(pid_list)) + ')'
            print query

            dirs = []
            cur.execute(query)
            for row in cur.fetchall():
                # print row
                count = int(row[0])
                did = str(row[1])
                # if args.separate_taxcounts_files:
                #      dir = prefix + str(ds_id)
                #
                #      if not os.path.isdir(dir):
                #          os.mkdir(dir)

                # tax_id = row[2]
                # rank = q["rank"]
                tax_id_str = ''
                for k in range(2, len(row)):
                    tax_id_str += '_' + str(row[k])
                # print 'tax_id_str', tax_id_str
                if did in counts_lookup:
                    # sys.exit('We should not be here - Exiting')
                    if tax_id_str in counts_lookup[did]:
                        # unless pid was duplicated on CL
                        sys.exit('We should not be here - Exiting')
                    else:
                        counts_lookup[did][tax_id_str] = count

                else:
                    counts_lookup[did] = {}
                    counts_lookup[did][tax_id_str] = count

        metadata_lookup = go_custom_metadata(dids, pid, metadata_lookup)

    print('all_dids', all_dids)
    all_did_sql = "', '".join(all_dids)
    metadata_lookup = go_required_metadata(all_did_sql, metadata_lookup)


    if args.metadata_warning_only:
        for did in dids:
            if did in metadata_lookup:
                print 'metadata found for did', did
            else:
                print 'WARNING -- no metadata for did:', did
    else:

        write_json_files(prefix, all_dids, metadata_lookup, counts_lookup)

        rando = randrange(10000, 99999)
        write_all_metadata_file(metadata_lookup, rando)

        # only write here for default taxonomy: silva119
        # discovered this file is not used
        # if args.units == 'silva119':
        #    write_all_taxcounts_file(counts_lookup, rando)


def write_all_metadata_file(metadata_lookup, rando):
    original_metadata_lookup = read_original_metadata()
    md_file = os.path.join(args.json_file_path, NODE_DATABASE + "--metadata.json")

    if not args.no_backup:
        bu_file = os.path.join(args.json_file_path, NODE_DATABASE + "--metadata_" + today + '_' + str(rando) + ".json")
        print 'Backing up metadata file to', bu_file
        shutil.copy(md_file, bu_file)
    # print md_file
    for did in metadata_lookup:
        original_metadata_lookup[did] = metadata_lookup[did]

    # print(metadata_lookup)
    # f = open(md_file, 'w')
    #     try:
    #         json_str = json.dumps(original_metadata_lookup, ensure_ascii=False)
    #     except:
    #         json_str = json.dumps(original_metadata_lookup)

    with io.open(md_file, 'w', encoding='utf-8') as f:
        try:
            f.write(json.dumps(original_metadata_lookup))
        except:
            f.write(json.dumps(original_metadata_lookup, ensure_ascii=False))
        finally:
            pass
    print 'writing new metadata file'
    # f.write(json_str.encode('utf-8').strip()+"\n")
    f.close()


def write_all_taxcounts_file(counts_lookup, rando):
    original_counts_lookup = read_original_taxcounts()

    tc_file = os.path.join(args.json_file_path, NODE_DATABASE + "--taxcounts_silva119.json")
    if not args.no_backup:
        bu_file = os.path.join(args.json_file_path,
                               NODE_DATABASE + "--taxcounts_silva119" + today + '_' + str(rando) + ".json")
        print 'Backing up taxcount file to', bu_file
        shutil.copy(tc_file, bu_file)
    for did in counts_lookup:
        original_counts_lookup[did] = counts_lookup[did]
    json_str = json.dumps(original_counts_lookup)
    # print(json_str)
    f = open(tc_file, 'w')  # this will delete taxcounts file!
    print 'writing new taxcount file'
    f.write(json_str + "\n")
    f.close()


def write_json_files(prefix, dids, metadata_lookup, counts_lookup):
    for did in dids:
        file_path = os.path.join(prefix, str(did) + '.json')
        print 'writing new file', file_path
        f = open(file_path, 'w')
        # print
        # print did, counts_lookup[did]
        if did in counts_lookup:
            my_counts_str = json.dumps(counts_lookup[did])
        else:
            my_counts_str = json.dumps({})
        if did in metadata_lookup:
            try:
                my_metadata_str = json.dumps(metadata_lookup[did])
            except:
                my_metadata_str = json.dumps(metadata_lookup[did], ensure_ascii=False)
        else:
            print 'WARNING -- no metadata for dataset:', did
            my_metadata_str = json.dumps({})
        # f.write('{"'+str(did)+'":'+mystr+"}\n")
        f.write('{"taxcounts":' + my_counts_str + ', "metadata":' + my_metadata_str + '}' + "\n")
        f.close()


def go_required_metadata(did_sql, metadata_lookup):
    """
        metadata_lookup_per_dsid[dsid][metadataName] = value            

    """

    required_metadata_fields = get_required_metadata_fields()
    req_query = "SELECT dataset_id, " + ', '.join(
        required_metadata_fields) + " from required_metadata_info WHERE dataset_id in ('%s')"
    query = req_query % (did_sql)
    print(query)
    cur.execute(query)
    for row in cur.fetchall():
        did = str(row[0])
        if did not in metadata_lookup:
            metadata_lookup[did] = {}
        for x, f in enumerate(required_metadata_fields):
            value = row[x + 1]
            metadata_lookup[did][f] = str(value)

    return metadata_lookup


def get_required_metadata_fields():
    q = "SHOW fields from required_metadata_info"
    cur.execute(q)
    md_fields = []
    fields_not_wanted = ['required_metadata_id', 'dataset_id', 'created_at', 'updated_at']
    for row in cur.fetchall():
        if row[0] not in fields_not_wanted:
            md_fields.append(row[0])
    return md_fields


def go_custom_metadata(did_list, pid, metadata_lookup):
    custom_table = 'custom_metadata_' + pid
    q = "show tables like '" + custom_table + "'"
    cur.execute(q)
    table_exists = cur.fetchall()
    if not table_exists:
        return metadata_lookup

    field_collection = ['dataset_id']
    cust_metadata_lookup = {}
    query = cust_pquery % (pid)
    cur.execute(query)
    for row in cur.fetchall():
        pid = str(row[0])
        field = row[1]
        if field != 'dataset_id':
            field_collection.append(field.strip())

    # print 'did_list', did_list
    # print 'field_collection', field_collection

    cust_dquery = "SELECT `" + '`, `'.join(field_collection) + "` from " + custom_table
    # print cust_dquery
    # try:
    cur.execute(cust_dquery)

    # print 'metadata_lookup1', metadata_lookup
    for row in cur.fetchall():
        # print row
        did = str(row[0])
        if did in did_list:

            for y, f in enumerate(field_collection):
                # cnt = i

                if f != 'dataset_id':
                    # if row[i]:
                    value = str(row[y])
                    # else:
                    #    value = None
                    # print 'XXX', did, i, f, value

                    if did in metadata_lookup:
                        metadata_lookup[did][f] = value
                    else:
                        metadata_lookup[did] = {}
                        metadata_lookup[did][f] = value

        # except:
        #    print 'could not find or read', table, 'Skipping'
    print
    # print 'metadata_lookup2', metadata_lookup
    # sys.exit()
    return metadata_lookup


def read_original_taxcounts():
    file_path1 = os.path.join(args.json_file_path, NODE_DATABASE + '--taxcounts_silva119.json')
    try:
        with open(file_path1) as data_file:
            data = json.load(data_file)
    except:

        file_path2 = os.path.join(args.json_file_path, NODE_DATABASE + '--taxcounts.json')
        print "could not read json file", file_path1, 'Now Trying', file_path2
        try:
            with open(file_path2) as data_file:
                data = json.load(data_file)
        except:
            print "could not read json file", file_path2, '--Exiting'
            sys.exit(1)
    return data


def read_original_metadata():
    file_path = os.path.join(args.json_file_path, NODE_DATABASE + '--metadata.json')
    try:
        with open(file_path) as data_file:
            data = json.load(data_file)
    except:
        print "could not read json file", file_path, '-Exiting'
        sys.exit(1)
    return data


def get_dataset_ids(pid):
    q = "SELECT dataset_id from dataset where project_id='" + str(pid) + "'"
    # print q
    cur.execute(q)
    dids = []
    numrows = cur.rowcount
    if numrows == 0:
        sys.exit('No data found for pid ' + str(pid))
    for row in cur.fetchall():
        dids.append(str(row[0]))

    return dids


#
#
#
if __name__ == '__main__':

    myusage = """
        -pids/--pids  [list of comma separated pids]
                
        -json_file_path/--json_file_path   json files path [Default: ../json]
        -host/--host        vampsdb, vampsdev    dbhost:  [Default: localhost]
        -units/--tax-units  silva119, or rdp2.6   [Default:silva119]
        
    count_lookup_per_dsid[dsid][rank][taxid] = count

    This script will add a project to ../json/<NODE-DATABASE>/<DATASET-NAME>.json JSON object
    But ONLY if it is already in the MySQL database.
    
    To add a new project to the MySQL database:
    If already GASTed:
        use ./upload_project_to_database.py in this directory
    If not GASTed
         use py_mbl_sequencing_pipeline custom scripts

    """

    parser = argparse.ArgumentParser(description="", usage=myusage)

    parser.add_argument("-pids", "--pids",
                        required=True, action="store", dest="pids_str", default='',
                        help="""ProjectID (used with -add)""")

    parser.add_argument("-no_backup", "--no_backup",
                        required=False, action="store_true", dest="no_backup", default=False,
                        help="""no_backup of group files: taxcounts and metadata""")
    parser.add_argument("-metadata_warning_only", "--metadata_warning_only",
                        required=False, action="store_true", dest="metadata_warning_only", default=False,
                        help="""warns of datasets with no metadata""")
    parser.add_argument("-json_file_path", "--json_file_path",
                        required=False, action='store', dest="json_file_path", default='../../json',
                        help="Not usually needed if -host is accurate")
    # for vampsdev"  /groups/vampsweb/vampsdev_node_data/json
    parser.add_argument("-host", "--host",
                        required=False, action='store', dest="dbhost", default='localhost',
                        help="choices=['vampsdb', 'vampsdev', 'localhost']")
    parser.add_argument("-units", "--tax_units",
                        required=False, action='store', choices=['silva119', 'rdp2.6'], dest="units",
                        default='silva119',
                        help="Default: 'silva119'; only other choice available is 'rdp2.6'")
    parser.add_argument("-dco", "--dco",
                        required=False, action='store_true', dest="dco", default=False,
                        help="")
    # if len(sys.argv[1:]) == 0:
    #     print myusage
    #     sys.exit()
    args = parser.parse_args()

    if args.dbhost == 'vamps' or args.dbhost == 'vampsdb':
        args.json_file_path = '/groups/vampsweb/vamps_node_data/json'
        dbhost = 'vampsdb'
        args.NODE_DATABASE = 'vamps2'

    elif args.dbhost == 'vampsdev':
        args.json_file_path = '/groups/vampsweb/vampsdev_node_data/json'
        args.NODE_DATABASE = 'vamps2'
        dbhost = 'bpcweb7'
    elif args.dbhost == 'localhost' and (
            socket.gethostname() == 'Annas-MacBook.local' or socket.gethostname() == 'Annas-MacBook-new.local'):
        args.NODE_DATABASE = 'vamps2'
        dbhost = 'localhost'
    else:
        dbhost = 'localhost'
        args.NODE_DATABASE = 'vamps_development'
    if args.units == 'silva119':
        args.files_prefix = os.path.join(args.json_file_path, args.NODE_DATABASE + "--datasets_silva119")
    elif args.units == 'rdp2.6':
        args.files_prefix = os.path.join(args.json_file_path, args.NODE_DATABASE + "--datasets_rdp2.6")
    else:
        sys.exit('UNITS ERROR: ' + args.units)
    print "\nARGS: dbhost  =", dbhost
    print "\nARGS: NODE_DATABASE  =", args.NODE_DATABASE
    print "ARGS: json_file_path =", args.json_file_path
    if os.path.exists(args.json_file_path):
        print '** Validated json_file_path **'
    else:
        print myusage
        print "Could not find json directory: '", args.json_file_path, "'-Exiting"
        sys.exit(-1)
    print "ARGS: units =", args.units

    db = MySQLdb.connect(host=dbhost,  # your host, usually localhost
                         read_default_file="~/.my.cnf_node")
    cur = db.cursor()
    if args.NODE_DATABASE:
        NODE_DATABASE = args.NODE_DATABASE
    else:
        cur.execute("SHOW databases like 'vamps%'")
        dbs = []
        print myusage
        db_str = ''
        for i, row in enumerate(cur.fetchall()):
            dbs.append(row[0])
            db_str += str(i) + '-' + row[0] + ';  '
        print db_str
        db_no = input("\nchoose database number: ")
        if int(db_no) < len(dbs):
            NODE_DATABASE = dbs[db_no]
        else:
            sys.exit("unrecognized number -- Exiting")

    print
    cur.execute("USE " + NODE_DATABASE)

    # out_file = "tax_counts--"+NODE_DATABASE+".json"
    # in_file  = "../json/tax_counts--"+NODE_DATABASE+".json"

    print 'DATABASE:', NODE_DATABASE

    if args.dco:
        args.pids_str = get_dco_pids()

    go_add(NODE_DATABASE, args.pids_str)