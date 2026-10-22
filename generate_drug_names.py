import sys
import json
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def clean_text(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', str(s)).strip()

def normalize_key(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s

def extract_base_name(name):
    if not name:
        return ""
    cleaned = clean_text(name)
    cleaned = re.sub(r'(?i)\s+(inj\.?|tab\.?|cap\.?|cream|gel|syrup|drop(s)?|suspension|infusion|solution|spray)\b.*$', '', cleaned)
    cleaned = re.sub(r'(?i)\s+\d+(\.\d+)?\s*(mg|g|mcg|ml|iu|ui|%|iu\/ml|mg\/ml|meq)\b.*$', '', cleaned)
    cleaned = re.sub(r'\s+\d+$', '', cleaned)
    return cleaned.strip()

print("Đang đọc drugs_catalog.cleaned.json...")
with open('drugs_catalog.cleaned.json', 'r', encoding='utf-8') as f:
    raw_drugs = json.load(f)

# Gom nhóm theo tên thuốc
drugs_map = {}
for item in raw_drugs:
    dname = clean_text(item.get("drugName"))
    if not dname:
        continue
    
    key = normalize_key(dname)
    if not key:
        continue

    if key not in drugs_map:
        drugs_map[key] = {
            "name": dname,
            "base_name": extract_base_name(dname),
            "active_ingredients": set(),
            "strengths": set(),
            "dosage_forms": set(),
        }
    
    entry = drugs_map[key]
    ai = clean_text(item.get("activeIngredient"))
    if ai:
        entry["active_ingredients"].add(ai)
    st = clean_text(item.get("strength"))
    if st:
        entry["strengths"].add(st)
    df = clean_text(item.get("dosageForm"))
    if df:
        entry["dosage_forms"].add(df)

drug_records = []
simple_names_set = set()

for key, val in drugs_map.items():
    # Rút gọn hoạt chất: nếu có nhiều, lấy chuỗi ngắn gọn hoặc danh sách
    ai_list = sorted(list(val["active_ingredients"]))
    ai_str = "; ".join(ai_list[:3]) if ai_list else ""
    st_list = sorted(list(val["strengths"]))
    st_str = ", ".join(st_list[:3]) if st_list else ""
    df_list = sorted(list(val["dosage_forms"]))
    df_str = ", ".join(df_list[:2]) if df_list else ""

    drug_records.append({
        "name": val["name"],
        "base_name": val["base_name"],
        "active_ingredient": ai_str,
        "strength": st_str,
        "dosage_form": df_str
    })
    
    simple_names_set.add(val["name"])
    if val["base_name"] and len(val["base_name"]) >= 3:
        simple_names_set.add(val["base_name"])

# Sắp xếp
drug_records.sort(key=lambda x: x["name"].lower())
simple_names_list = sorted(list(simple_names_set), key=lambda x: x.lower())

# Ghi file drug_names.json (chứa thông tin chuẩn hóa để compare chính xác)
with open("drug_names.json", "w", encoding="utf-8") as f:
    json.dump(drug_records, f, ensure_ascii=False, indent=2)

# Ghi file drug_names_list.json (chỉ danh sách tên để tra nhanh hoặc làm từ điển autocomplete)
with open("drug_names_list.json", "w", encoding="utf-8") as f:
    json.dump(simple_names_list, f, ensure_ascii=False, indent=2)

import os
size_main = os.path.getsize("drug_names.json") / (1024 * 1024)
size_list = os.path.getsize("drug_names_list.json") / (1024 * 1024)
print(f"File drug_names.json: {len(drug_records)} bản ghi, {size_main:.2f} MB")
print(f"File drug_names_list.json: {len(simple_names_list)} tên, {size_list:.2f} MB")
