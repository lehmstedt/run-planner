"""Range-read Overture Maps GeoParquet files on AWS Open Data for a bounding box."""
import io, re, sys, json, requests
import pyarrow.parquet as pq

BUCKET = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
S = requests.Session()

def latest_release():
    x = S.get(f"{BUCKET}/?list-type=2&prefix=release/&delimiter=/", timeout=60).text
    return sorted(re.findall(r"<Prefix>(release/[^<]+)/</Prefix>", x))[-1]

def list_files(prefix):
    keys, token = [], None
    while True:
        u = f"{BUCKET}/?list-type=2&prefix={prefix}"
        if token: u += "&continuation-token=" + requests.utils.quote(token)
        x = S.get(u, timeout=60).text
        keys += re.findall(r"<Key>([^<]+\.parquet)</Key>", x)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
        if not m: return keys
        token = m.group(1)

class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        self.size = int(S.head(url, timeout=60).headers["Content-Length"])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        if n == 0 or self.pos >= self.size: return b""
        end = min(self.pos + n, self.size) - 1
        for _ in range(5):
            try:
                r = S.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=120)
                r.raise_for_status(); break
            except Exception as e:
                print("retry", e, file=sys.stderr)
        self.pos += len(r.content)
        return r.content
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)

def _stat(rg_meta, names, col):
    i = names.index(col)
    st = rg_meta.column(i).statistics
    return (st.min, st.max) if st is not None and st.has_min_max else (None, None)

def read_bbox(theme, typ, bbox, columns=None):
    """bbox = (xmin, ymin, xmax, ymax). Yields pyarrow tables of rows intersecting bbox."""
    xmin, ymin, xmax, ymax = bbox
    rel = latest_release()
    files = list_files(f"{rel}/theme={theme}/type={typ}/")
    print(rel, theme, typ, len(files), "files", file=sys.stderr)
    import pyarrow.compute as pc
    for k in files:
        f = pq.ParquetFile(RangeFile(f"{BUCKET}/{k}"))
        md = f.metadata
        names = [md.schema.column(i).path for i in range(md.num_columns)]
        rgs = []
        for g in range(md.num_row_groups):
            rg = md.row_group(g)
            a, _ = _stat(rg, names, "bbox.xmin"); _, b = _stat(rg, names, "bbox.xmax")
            c, _ = _stat(rg, names, "bbox.ymin"); _, d = _stat(rg, names, "bbox.ymax")
            if a is None or (a <= xmax and b >= xmin and c <= ymax and d >= ymin):
                rgs.append(g)
        if not rgs: continue
        print(k.split("/")[-1][:40], len(rgs), "row groups", file=sys.stderr)
        t = f.read_row_groups(rgs, columns=columns)
        bb = t.column("bbox")
        m = pc.and_(pc.and_(pc.less_equal(pc.struct_field(bb, "xmin"), xmax), pc.greater_equal(pc.struct_field(bb, "xmax"), xmin)),
                    pc.and_(pc.less_equal(pc.struct_field(bb, "ymin"), ymax), pc.greater_equal(pc.struct_field(bb, "ymax"), ymin)))
        t = t.filter(m)
        if t.num_rows: yield t
