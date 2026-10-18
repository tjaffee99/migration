"""Shared helpers for the foreign-born stock pipeline (scripts/stock/).

Core idea: every source table is parsed into a *tree* of origin categories
(Total -> regions -> subregions -> countries -> sub-country units), with one value
per node.  ``finalize_tree`` then turns one tree into output rows with a ``level``
and ``parent_label`` such that, for every (year, geography, source):

    sum(level == 'country') + sum(level == 'residual') == total

Levels:
  total      the foreign-born total of the table
  region     first-level aggregates (continents / world regions as the source names them)
  subregion  deeper aggregates (Northern Europe, Caribbean, "Former Soviet Union, in Europe", ...)
  country    the first country-like unit on a branch
  subcountry a unit nested inside a country row (England inside United Kingdom, Azores inside
             Portugal (total), Hong Kong inside ACS "China", Canada-French inside Canada).  These
             nest and are NOT part of the country+residual partition.
  residual   "Other ...", "... n.e.c.", "not reported", or a derived remainder of an aggregate
             whose children do not add up to it (label ends with "(derived)").

Nodes whose value is not available (NA) for a year are dropped for that year and their
children are re-attached to the nearest available ancestor.
"""
import re

REGION_LABELS = {
    'Europe', 'Asia', 'Africa', 'Oceania', 'Latin America', 'Northern America', 'Americas',
}
SUBREGION_LABELS = {
    'Northern and Western Europe', 'Northern Europe', 'British Isles', 'Scandinavia',
    'Western Europe', 'Low countries', 'Southern and Eastern Europe', 'Southern Europe',
    'Eastern Europe', 'Eastern Asia', 'South Central Asia', 'South Eastern Asia', 'Western Asia',
    'Eastern Africa', 'Middle Africa', 'Northern Africa', 'Southern Africa', 'Western Africa',
    'Australia and New Zealand', 'Australia and New Zealand Subregion', 'Pacific Islands',
    'Melanesia', 'Micronesia (region)', 'Polynesia', 'Caribbean', 'Central America',
    'South America', 'Latin America', 'Northern America', 'Other Central America',
    'Other Northern America', 'Former Soviet Union, in Europe',
    'Former Soviet Union (part), South Central Asia', 'Former Soviet Union (part), Western Asia',
    'Asia (including Middle East)',
}
RESIDUAL_RE = re.compile(
    r'(n\.e\.c\.|n\.e\.c$|\bnec\b|^Other\b|^Other$|not reported|not specified|Not reported|'
    r'Born at sea|excl\. Atlantic Islands|^Atlantic Islands|West Indies n\.e\.c|'
    r'^Region or country not reported|\(derived\)|Country not specified|Europe, n\.e\.c|'
    r'Asia,n\.e\.c|^Middle East n\.e\.c|not tabulated|^West Indies$)', re.I)


def is_residual_label(label):
    return bool(RESIDUAL_RE.search(label))


class Node:
    __slots__ = ('label', 'parent', 'children', 'values', 'kind', 'meta')

    def __init__(self, label, parent=None, kind=None):
        self.label = label
        self.parent = parent
        self.children = []
        self.values = {}   # key (year or geo) -> int or None
        self.kind = kind   # optional forced classification: 'agg', 'country', 'residual'
        self.meta = {}
        if parent is not None:
            parent.children.append(self)

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def __repr__(self):
        return 'Node(%r)' % self.label


def build_tree_from_depths(rows, root_label='Total'):
    """rows: list of (label, depth, values_dict).  The first row must be the total."""
    root = Node(root_label)
    root.values = dict(rows[0][2])
    stack = [(-1, root)]
    for label, depth, vals in rows[1:]:
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1]
        n = Node(label, parent)
        n.values = dict(vals)
        stack.append((depth, n))
    return root


def build_tree_from_paths(items, root_label='Total'):
    """items: list of (path_tuple, key, value) where path_tuple excludes the root.
    Returns root.  Path elements are labels; trailing ':' already stripped."""
    root = Node(root_label)
    index = {(): root}
    for path, key, val in items:
        path = tuple(path)
        for i in range(1, len(path) + 1):
            p = path[:i]
            if p not in index:
                index[p] = Node(p[-1], index[p[:-1]])
        index[path].values[key] = val
    return root, index


def reparent(root, label, new_parent_label):
    """Move the (unique) node `label` under the node `new_parent_label`."""
    nodes = {n.label: n for n in root.walk()}
    n, p = nodes[label], nodes[new_parent_label]
    n.parent.children.remove(n)
    n.parent = p
    p.children.append(n)


def _present(node, key):
    v = node.values.get(key)
    return v is not None


def finalize_tree(root, key, source_id, derived_source_id=None, warn=None,
                  tolerance=0):
    """Return list of dict rows (origin_label, level, parent_label, count, source_id)
    for one key (year / geography).  Adds derived residual rows where an aggregate's
    present children do not sum to it.  ``warn`` is a list collecting warning strings."""
    if warn is None:
        warn = []
    derived_source_id = derived_source_id or (source_id + '_derived')
    out = []
    total = root.values.get(key)
    if total is None:
        return out
    out.append(dict(origin_label=root.label, level='total', parent_label='',
                    count=int(total), source_id=source_id))

    def present_children(node):
        """Children present for key, with absent intermediate nodes flattened."""
        res = []
        for c in node.children:
            if _present(c, key):
                res.append(c)
            else:
                res.extend(present_children(c))
        return res

    def has_country_desc(node):
        for c in present_children(node):
            if classify(c) == 'country' or has_country_desc(c):
                return True
        return False

    def classify(node):
        if node.kind:
            return node.kind
        lab = node.label
        if is_residual_label(lab):
            return 'residual'   # becomes a subregion in emit() if it has country descendants
        if lab in SUBREGION_LABELS or lab in REGION_LABELS:
            return 'agg'
        if '(former' in lab and present_children(node):
            return 'agg'
        return 'country'

    def emit(node, parent_label, depth_region, inside_country):
        v = int(node.values[key])
        kids = present_children(node)
        cls = classify(node)
        if inside_country:
            level = 'subcountry'
        elif cls == 'residual' and not has_country_desc(node):
            out.append(dict(origin_label=node.label, level='residual', parent_label=parent_label,
                            count=v, source_id=source_id))
            return  # descendants of a residual are not emitted
        elif cls == 'country':
            level = 'country'
        else:
            level = 'region' if depth_region == 1 else 'subregion'
        out.append(dict(origin_label=node.label, level=level, parent_label=parent_label,
                        count=v, source_id=source_id))
        s = 0
        for c in kids:
            s += int(c.values[key])
            emit(c, node.label, depth_region + 1, inside_country or level == 'country'
                 or level == 'subcountry')
        if kids:
            gap = v - s
            if gap != 0:
                if abs(gap) <= tolerance:
                    pass
                if gap < 0:
                    warn.append('%s %s: children of %r sum to %d > %d' %
                                (source_id, key, node.label, s, v))
                lab = (node.label + ', remainder (derived)') if level in ('country', 'subcountry') \
                    else (node.label + ', country not specified (derived)')
                out.append(dict(origin_label=lab,
                                level='subcountry' if level in ('country', 'subcountry') else 'residual',
                                parent_label=node.label, count=gap, source_id=derived_source_id))
        elif level in ('region', 'subregion'):
            # aggregate with no country detail at all in this year
            out.append(dict(origin_label=node.label + ', country not specified (derived)',
                            level='residual', parent_label=node.label, count=v,
                            source_id=derived_source_id))

    s = 0
    for c in present_children(root):
        s += int(c.values[key])
        emit(c, root.label, 1, False)
    gap = int(total) - s
    if gap != 0:
        if gap < 0:
            warn.append('%s %s: children of Total sum to %d > %d' % (source_id, key, s, total))
        out.append(dict(origin_label='Total, origin not specified (derived)', level='residual',
                        parent_label=root.label, count=gap, source_id=derived_source_id))
    return out


def tree_rows(labels, est, moe, source_id, rename=None, warn=None):
    """labels: {n: path}; est/moe: {n: value}.  Returns finalized rows with moe."""
    items = []
    for n, path in sorted(labels.items()):
        if n == 1:
            continue
        items.append((path, 'v', est.get(n)))
    root, index = build_tree_from_paths(items)
    root.values['v'] = est.get(1)
    node_moe = {id(root): moe.get(1) if moe else None}
    for n, path in labels.items():
        if path:
            node_moe[id(index[tuple(path)])] = moe.get(n) if moe else None
    # disambiguate labels equal to their parent's, and region-vs-country 'Micronesia'
    for node in list(root.walk()):
        if node.parent is not None and node.label == node.parent.label:
            node.label = node.label + ', n.e.c.'
        if node.label == 'Micronesia' and node.parent is not None and \
                any(s.label == 'Melanesia' for s in node.parent.children):
            node.label = 'Micronesia (region)'
        if rename and node.label in rename:
            node.label = rename[node.label]
    lab_moe = {}
    for node in root.walk():
        lab_moe.setdefault(node.label, node_moe.get(id(node)))
    rr = finalize_tree(root, 'v', source_id, warn=warn)
    for r in rr:
        m = None if r['source_id'].endswith('_derived') else lab_moe.get(r['origin_label'])
        r['moe'] = '' if m is None else m
    return rr



def check_partition(rows):
    """Return (total, country+residual sum) for rows of one key."""
    tot = [r['count'] for r in rows if r['level'] == 'total']
    part = sum(r['count'] for r in rows if r['level'] in ('country', 'residual'))
    return (tot[0] if tot else None), part


def parse_num(v):
    """Census xls cell -> int or None.  '(NA)', '(X)', footnote-only cells -> None; '-' -> 0."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).strip().replace(',', '')
    if s in ('-', '–', '—'):
        return 0
    if s == '' or s.startswith('(') or s.startswith('/'):
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


FOOTNOTE_TAIL = re.compile(r'(\s+\d+(\s*,\s*\d+)*\s*$|\s*/\d+\s*$)')


def clean_label(raw):
    """Strip leading dots/spaces, trailing dot leaders and footnote markers."""
    s = str(raw)
    s = s.replace('…', '...')
    s = re.sub(r'^[\s\.]+', '', s)
    s = re.sub(r'[\s\.]*\.{3,}[\s\.]*$', '', s)   # dot leaders
    s = re.sub(r'\.{3,}.*$', '', s)
    s = s.strip()
    s = FOOTNOTE_TAIL.sub('', s).strip()
    s = re.sub(r'\s+', ' ', s)
    if s.endswith('n.e.c'):
        s += '.'
    return s


def indent_depth(raw):
    m = re.match(r'^[\s\.…]*', str(raw))
    return len(m.group(0)) if m else 0


STATE_FIPS = {
    'Alabama': '01', 'Alaska': '02', 'Arizona': '04', 'Arkansas': '05', 'California': '06',
    'Colorado': '08', 'Connecticut': '09', 'Delaware': '10', 'District of Columbia': '11',
    'Florida': '12', 'Georgia': '13', 'Hawaii': '15', 'Idaho': '16', 'Illinois': '17',
    'Indiana': '18', 'Iowa': '19', 'Kansas': '20', 'Kentucky': '21', 'Louisiana': '22',
    'Maine': '23', 'Maryland': '24', 'Massachusetts': '25', 'Michigan': '26', 'Minnesota': '27',
    'Mississippi': '28', 'Missouri': '29', 'Montana': '30', 'Nebraska': '31', 'Nevada': '32',
    'New Hampshire': '33', 'New Jersey': '34', 'New Mexico': '35', 'New York': '36',
    'North Carolina': '37', 'North Dakota': '38', 'Ohio': '39', 'Oklahoma': '40', 'Oregon': '41',
    'Pennsylvania': '42', 'Rhode Island': '44', 'South Carolina': '45', 'South Dakota': '46',
    'Tennessee': '47', 'Texas': '48', 'Utah': '49', 'Vermont': '50', 'Virginia': '51',
    'Washington': '53', 'West Virginia': '54', 'Wisconsin': '55', 'Wyoming': '56',
    'Puerto Rico': '72',
}
FIPS_STATE = {v: k for k, v in STATE_FIPS.items()}
