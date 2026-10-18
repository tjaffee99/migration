"""Readers for ACS B05006 / B05002 (data.census.gov table API JSON, and the 2005-2009
sequence-based summary files) and Decennial 2000 SF3 PCT019 / P021."""
import csv, glob, io, json, os, re, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'data', 'raw')

SENTINELS = {'-666666666', '-999999999', '-888888888', '-222222222', '-333333333',
             '-555555555', '-111111111', '-777777777', '*****', 'N', '(X)', '-', ''}


def to_int(s):
    if s is None:
        return None
    s = str(s).strip()
    if s in SENTINELS or s.startswith('-') and len(s) >= 9:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def label_path(label):
    """'Estimate!!Total:!!Europe:!!Northern Europe:!!Ireland' -> ('Europe','Northern Europe','Ireland')"""
    parts = [p.strip().rstrip(':').strip() for p in label.split('!!')]
    if parts and parts[0] in ('Estimate', 'Margin of Error'):
        parts = parts[1:]
    if parts and parts[0] == 'Total':
        parts = parts[1:]
    return tuple(parts)


def load_groups(path, table):
    """var number (int) -> label path tuple, from api.census.gov groups JSON."""
    g = json.load(open(path))['variables']
    out = {}
    for k, v in g.items():
        m = re.match(r'^%s_(\d{3})E$' % table, k)
        if m:
            out[int(m.group(1))] = label_path(v['label'])
    return out


def load_api_table(path, table):
    """Returns {geo_id: {'name':..., 'E': {n: est}, 'M': {n: moe}}}"""
    d = json.load(open(path))['response']['data']
    hdr = d[0]
    out = {}
    for row in d[1:]:
        r = dict(zip(hdr, row))
        geo = r.get('GEO_ID')
        rec = {'name': r.get('NAME'), 'E': {}, 'M': {}}
        for k, v in r.items():
            m = re.match(r'^%s_(\d{3})([EM])$' % table, k)
            if m:
                rec[m.group(2)][int(m.group(1))] = to_int(v)
        out[geo] = rec
    return out


# ---------------------------------------------------------------- 2005-2009 summary files
SF_SEQ = {2005: {'B05002': (11, 89 - 6, 15), 'B05006': (12, 89 - 6, 123)},
          2006: {'B05002': (20, 13 - 6, 15), 'B05006': (22, 7 - 6, 123)},
          2007: {'B05002': (23, 13 - 6, 15), 'B05006': (25, 7 - 6, 123)},
          2008: {'B05002': (23, 13 - 6, 15), 'B05006': (25, 7 - 6, 123)},
          2009: {'B05002': (23, 13 - 6, 15), 'B05006': (25, 7 - 6, 161)}}
# value = (sequence, 1-based offset of the table's first cell among the data cells, n cells)
# Start positions from the lookup files count the 6 identifier fields; 2005's file lists
# position 89 for B05006 in sequence 12 and 13 for B05002 in sequence 11.
SF_SEQ[2005]['B05002'] = (11, 13 - 6, 15)


def _geo_first_record(geo_head_path, year):
    raw = open(geo_head_path, 'rb').read().decode('latin-1')
    line = raw.splitlines()[0]
    # fixed width: FILEID(6) STUSAB(2) SUMLEVEL(3) COMPONENT(2) LOGRECNO(7)
    return dict(stusab=line[6:8], sumlevel=line[8:11], component=line[11:13],
                logrecno=line[13:20], line=line[:200])


def load_sf_table(year, table):
    """Read B05002 or B05006 for LOGRECNO 0000001 (nation in the US file, the state in each
    state file) for every state directory.  Returns {dir_name: {'stusab', 'E', 'M', 'geo'}}"""
    seq, off, n = SF_SEQ[year][table]
    base = os.path.join(RAW, 'acs_sf_2005_2009', str(year))
    out = {}
    for d in sorted(os.listdir(base)):
        dd = os.path.join(base, d)
        zips = [z for z in os.listdir(dd) if z.endswith('.zip') and
                (('%07d.2005-1yr' % seq) in z or ('%04d000.zip' % seq) in z)]
        if not zips:
            continue
        z = zipfile.ZipFile(os.path.join(dd, zips[0]))
        names = z.namelist()
        ef = [x for x in names if re.search(r'(^|/)e[^/]*\.txt$', x) or
              re.search(r'%07de\.2005-1yr$' % seq, x)]
        mf = [x for x in names if re.search(r'(^|/)m[^/]*\.txt$', x) or
              re.search(r'%07dm\.2005-1yr$' % seq, x)]
        assert len(ef) == 1 and len(mf) == 1, (year, d, names)
        rec = {'E': {}, 'M': {}}
        for kind, fn in (('E', ef[0]), ('M', mf[0])):
            txt = z.read(fn).decode('latin-1')
            for row in csv.reader(io.StringIO(txt)):
                if row[5] == '0000001':
                    rec['stusab'] = row[2].upper()
                    cells = row[6:]
                    for i in range(n):
                        rec[kind][i + 1] = to_int(cells[off - 1 + i])
                    break
        geo = glob.glob(os.path.join(dd, '*.head'))
        rec['geo'] = _geo_first_record(geo[0], year) if geo else None
        out[d] = rec
    return out


def load_sf_lookup_titles(year, table):
    """Line titles from the sequence/table lookup file, for cross-checking variable labels."""
    base = os.path.join(RAW, 'acs_sf_2005_2009')
    titles = {}
    if year == 2006 or year == 2009:
        fn = os.path.join(base, '2006_merge_5_6_final.txt' if year == 2006 else '2009_merge_5_6.txt')
        delim = '\t' if year == 2006 else ','
        for row in csv.reader(open(fn, encoding='latin-1'), delimiter=delim):
            if len(row) > 7 and row[1] == table:
                try:
                    ln = int(float(row[3]))
                except ValueError:
                    continue
                if ln > 0 and row[4] in ('0', '.', ''):
                    titles[ln] = row[7].strip().strip('"').rstrip(':').strip()
    else:
        import xlrd
        fn = {2005: '2005_Chapter_5_tables_summary_list.xls', 2007: '2007_merge_5_6_final.xls',
              2008: '2008_merge_5_6.xls'}[year]
        sh = xlrd.open_workbook(os.path.join(base, fn)).sheet_by_index(0)
        if year == 2005:
            return {}   # 2005 list has no line-level titles
        for r in range(1, sh.nrows):
            row = [sh.cell_value(r, c) for c in range(sh.ncols)]
            if str(row[1]).strip() != table:
                continue
            try:
                ln = int(float(row[3]))
            except (ValueError, TypeError):
                continue
            if ln > 0 and 'CELL' not in str(row[5]).upper():
                titles[ln] = str(row[7]).strip().rstrip(':').strip()
    return titles
