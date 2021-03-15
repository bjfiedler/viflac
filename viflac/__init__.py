# coding: utf-8

""" Common functions for the Systems Research and Architecture Group. """
from collections import defaultdict
import argparse
import logging
import os
import pathlib
import re
import subprocess
import sys
import tempfile

logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[1;41m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
logging.addLevelName( logging.DEBUG, "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
logging.addLevelName( logging.INFO, "\033[1;34m%s\033[1;0m" % logging.getLevelName(logging.INFO))
logging.basicConfig(level=logging.DEBUG)

__version__ = '0.1.2'

data = {}
counter = 0
tag_keys = set()

def add_file(path):
    logging.info("+f %s", path)
    global counter
    counter += 1
    elem = defaultdict(lambda:"")
    elem['__id'] = counter
    elem['__path'] = path
    elem['__filename'] = str(path)
    get_flags(elem)
    data[counter] = elem

def get_flags(elem):
    result = subprocess.check_output(['metaflac', '--export-tags-to=-', '--no-utf8-convert',
                                      str(elem['__path'])])
    for line in result.decode().strip().split('\n'):
        logging.debug("line: %s", line)
        k, v = line.split('=', 1)
        elem[k] = v
        tag_keys.add(k)
    print(result)

def add_dir(path):
    logging.info('i  %s', path)
    for f in sorted(path.iterdir()):
        logging.info(' f %s', f)
        if f.is_dir():
            add_dir(f)
        elif f.is_file() and f.name.endswith('flac'):
            add_file(f)

def print_table(outfile):
    columns = ['__id', '__filename'] + [x for x in tag_keys]
    lengths = {}
    for column in columns:
        item_max = max([len(str(x[column])) for x in data.values()])
        lengths[column] = max(len(column), item_max)
    logging.info("lengths: %s", lengths)
    data[0] = {x: x for x in columns}
    for idx in sorted(data):
        row = data[idx]
        cols = []
        for col in columns:
            cols.append(f'{str(row[col]):{lengths[col]}}')
        line = "|".join(cols)
        outfile.write(line.encode())
        outfile.write(b'\n')

def start_editor(filename):
    editor = os.environ.get('EDITOR', 'nano')
    subprocess.check_call([editor, filename])

def read_back(filename):
    with open(filename, 'r') as infile:
        content = infile.read()
        lines = content.strip().split('\n')
        header = [x.strip() for x in lines[0].split('|')]
        logging.info('headers: %s', header)
        if header[0] != '__id':
            logging.error('id not in firt column')
        for line in lines[1:]:
            cols = [x.strip() for x in line.split('|')]
            logging.info('cols: %s', cols)
            idx = int(cols[0])
            for col in range(1, len(cols)):
                if header[col] == '__id':
                    continue
                try:
                    data[idx][header[col]] = int(cols[col])
                except:
                    data[idx][header[col]] = cols[col]
                    pass

def produce_metaflac_format(idx):
    rows = []
    for k, v in data[idx].items():
        if k.startswith('__'):
            continue
        rows.append(f'{k}={v}')
    return "\n".join(rows) + '\n'

def write_metaflac():
    for entry in data.values():
        subprocess.run(
            ['metaflac', '--remove-all-tags', '--import-tags-from=-', '--no-utf8-convert', str(entry['__path'])],
            check=True,
            input=entry['__metaflac'].encode())

def move_files():
    for entry in data.values():
        new_path = entry['__filename'].format(**entry)
        new_path = re.sub('\s', '_', new_path)
        new_path = pathlib.Path(new_path)
        logging.info("new path: %s", new_path)
        if entry['__path'] == new_path:
            continue
        new_path.parent.mkdir(parents=True, exist_ok=True)
        entry['__path'].rename(new_path)
        logging.info('renamed %s -> %s', entry['__path'], new_path)

def main(argv):
    """Provide a simple cli interface for SRA functions."""

    parser = argparse.ArgumentParser(prog=sys.argv[0],
                                     description=sys.modules[__name__].__doc__,
                                     )
    parser.add_argument('FILE', nargs='+')
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args(argv)

    for f in args.FILE:
        path = pathlib.Path(f)
        if path.is_file():
            add_file(path)
        if path.is_dir():
            add_dir(path)
    outfile = tempfile.NamedTemporaryFile(delete=False)
    print_table(outfile)
    filename = outfile.name
    logging.info('filename: %s', filename)
    outfile.close()
    start_editor(filename)
    read_back(filename)

    del data[0]
    for k in data:
        logging.info("generate metaflac for %s", data[k]['__path'])
        data[k]['__metaflac'] = produce_metaflac_format(k)
        print(data[k]['__metaflac'])
    write_metaflac()
    move_files()
