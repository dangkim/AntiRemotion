import json

def fix_string(s):
    if not isinstance(s, str):
        return s
    try:
        # PowerShell might have messed up utf-8 strings by reading them as cp1252 and writing as utf-8
        return s.encode('cp1252').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # If it fails, let's try latin-1
        try:
            return s.encode('latin-1').decode('utf-8')
        except:
            return s

def fix_dict(d):
    for k, v in d.items():
        if isinstance(v, str):
            d[k] = fix_string(v)
        elif isinstance(v, list):
            d[k] = fix_list(v)
        elif isinstance(v, dict):
            d[k] = fix_dict(v)
    return d

def fix_list(l):
    for i in range(len(l)):
        if isinstance(l[i], str):
            l[i] = fix_string(l[i])
        elif isinstance(l[i], list):
            l[i] = fix_list(l[i])
        elif isinstance(l[i], dict):
            l[i] = fix_dict(l[i])
    return l

with open('shots.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data = fix_dict(data)

with open('shots.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Fixed double encoding in shots.json.")
