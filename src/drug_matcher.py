import os
import sys
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from rapidfuzz import fuzz, process, utils

def normalize_text(text: str) -> str:
    """Chuẩn hóa văn bản về chữ thường, bỏ khoảng trắng thừa"""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tăng khả năng so khớp mờ khi OCR bị mất dấu"""
    import unicodedata
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def check_ingredient_match(inside: str, target_ai: str) -> float:
    """
    Kiểm tra độ trùng khớp giữa chuỗi gợi ý hoạt chất trên đơn thuốc và hoạt chất trong từ điển.
    Hỗ trợ cả trường hợp đơn hoạt chất lẫn phối hợp đa hoạt chất.
    """
    if not inside or not target_ai:
        return 0.0

    s1 = strip_accents(inside.lower())
    s2 = strip_accents(target_ai.lower())

    score1 = fuzz.partial_ratio(s1, s2)
    score2 = fuzz.token_set_ratio(s1, s2)
    best_score = max(score1, score2)

    # Đếm số lượng từ khóa dược học trùng nhau (độ dài >= 3)
    tokens1 = set(re.findall(r'\b[a-zA-Z]{3,}\b', s1))
    tokens2 = set(re.findall(r'\b[a-zA-Z]{3,}\b', s2))
    # Bỏ qua các từ stopword thông thường
    stopwords = {"mg", "ml", "goi", "vien", "chai", "ong", "hop", "moi", "chua", "chiet", "xuat", "ngay", "uong"}
    tokens1 = {t for t in tokens1 if t not in stopwords}
    tokens2 = {t for t in tokens2 if t not in stopwords}

    if tokens1 and tokens2:
        overlap = len(tokens1.intersection(tokens2))
        if overlap >= 2:
            best_score = max(best_score, 80.0 + min(overlap * 4.0, 19.0))
        elif overlap == 1 and len(tokens1) <= 2:
            best_score = max(best_score, 82.0)

    return min(best_score, 100.0)

def parse_drug_line_details(raw_line: str) -> Dict[str, Any]:
    """
    Phân tách thông minh một dòng kê thuốc:
    - Bỏ số thứ tự đầu dòng (1., 2), 03...)
    - Bóc tách nội dung trong ngoặc đơn (hoạt chất, hàm lượng, dạng dùng)
    - Bóc tách liều dùng, cách dùng (uống, tiêm, ngày 2 lần...)
    - Bóc tách số lượng (x 14 viên, SL: 10, 20 viên...)
    - Bóc tách hàm lượng (500mg, 1g, 40mg, 100ml...)
    - Trả về tên thuốc sạch và hoạt chất gợi ý để tra cứu từ điển
    """
    if not raw_line:
        return {
            "stt": "",
            "clean_name": "",
            "brand_no_strength": "",
            "strength": "",
            "quantity": "",
            "usage": "",
            "bracket_content": "",
            "raw_line": ""
        }

    text = raw_line.strip()

    # 1. Tách số thứ tự ở đầu dòng (ví dụ: '1.', '02/', '3)', '4 - ')
    stt = ""
    stt_match = re.match(r'^([\d]+)[\.\)\/\-\s]+(.*)$', text)
    if stt_match:
        stt = stt_match.group(1)
        text = stt_match.group(2).strip()

    # 2. Tách hướng dẫn sử dụng / cách dùng
    usage = ""
    usage_match = re.search(r'(?i)(?:uống|tiêm|ngậm|nhỏ|bôi|đặt|uống:|cách dùng:|hướng dẫn:|ngày uống)\s*(.*)$', text)
    if usage_match:
        usage = usage_match.group(0).strip()
        text = text[:usage_match.start()].strip()

    # 3. Tách số lượng & đơn vị tính
    quantity = ""
    qty_patterns = [
        r'(?i)(?:x|\*|sl|số lượng|soluong|sl:)\s*[:\s]*(\d+[\s\w]*)',
        r'(?i)[-–—:]\s*(\d+\s*(?:viên|gói|ống|chai|lọ|hộp|tuýp|vỉ|bình|liều|tép|ml))\b',
        r'(?i)\b(\d+)\s*(?:viên|gói|ống|chai|lọ|hộp|tuýp|vỉ|bình)\b'
    ]
    for pattern in qty_patterns:
        m = re.search(pattern, text)
        if m:
            quantity = m.group(0).strip()
            text = text[:m.start()].strip() + " " + text[m.end():].strip()
            break

    # 4. Tách nội dung trong ngoặc đơn (hoạt chất / quy cách / hàm lượng)
    # Dùng regex greedy từ dấu '(' đầu tiên đến dấu ')' cuối cùng
    bracket_content = ""
    paren_match = re.search(r'\((.*)\)', text)
    if paren_match:
        bracket_content = paren_match.group(1).strip()
        brand_text = (text[:paren_match.start()] + ' ' + text[paren_match.end():]).strip()
    else:
        brand_text = text.strip()

    # 5. Tách hàm lượng (strength) từ cả bracket_content lẫn brand_text
    strength = ""
    str_pattern = r'(?i)\b(\d+(?:\.\d+)?(?:\+\d+(?:\.\d+)?)?\s*(?:mg|g|mcg|ml|iu|ui|%|mg\/ml|iu\/ml|meq))\b'
    # Tìm trong brand_text trước
    str_m = re.search(str_pattern, brand_text)
    if str_m:
        strength = str_m.group(1).strip()
    elif bracket_content:
        # Nếu không có trong brand_text, tìm trong ngoặc
        str_m2 = re.search(str_pattern, bracket_content)
        if str_m2:
            strength = str_m2.group(1).strip()
        else:
            # Tìm số đơn thuần trong ngoặc ví dụ '(Trimebutine 200)'
            num_m = re.search(r'\b(\d{2,4})\b', bracket_content)
            if num_m:
                strength = num_m.group(1).strip()

    # 6. Làm sạch tên thương mại (clean_name)
    clean_name = re.sub(r'[\(\)\[\],;:\-_]+', ' ', brand_text)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()

    # Tên thương mại loại bỏ hoàn toàn hàm lượng
    brand_no_strength = re.sub(r'(?i)\s*\d+(?:\.\d+)?(?:\+\d+(?:\.\d+)?)?\s*(mg|g|mcg|ml|iu|ui|%|mg\/ml|iu\/ml|meq)\b.*$', '', clean_name).strip()

    return {
        "stt": stt,
        "clean_name": clean_name,
        "brand_no_strength": brand_no_strength,
        "strength": strength,
        "quantity": quantity.strip(" -–:"),
        "usage": usage,
        "bracket_content": bracket_content,
        "raw_line": raw_line
    }

class DrugCatalogMatcher:
    """
    Engine so khớp tên thuốc với kho từ điển 44.000+ thuốc chuẩn của Cục Quản lý Dược (DAV).
    Hỗ trợ đối chiếu đa tầng:
    1. Exact / Base Name Match
    2. Substring & Token Match (Xử lý tên viết tắt / ghép tên hãng: Ahngookpapaze -> Papaze)
    3. Active Ingredient Cross-Check (Đối chiếu chéo thành phần hoạt chất trong ngoặc đơn)
    4. Fuzzy RapidFuzz Match dự phòng.
    """
    _instance = None

    @classmethod
    def get_instance(cls, dict_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = DrugCatalogMatcher(dict_path)
        return cls._instance

    def __init__(self, dictionary_path: Optional[str] = None):
        if not dictionary_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            candidate_paths = [
                os.path.join(base_dir, "..", "drug_names.json"),
                os.path.join(base_dir, "drug_names.json"),
                os.path.join(os.getcwd(), "drug_names.json")
            ]
            for p in candidate_paths:
                if os.path.exists(p):
                    dictionary_path = p
                    break

        if not dictionary_path or not os.path.exists(dictionary_path):
            raise FileNotFoundError(f"Không tìm thấy file từ điển thuốc tại {dictionary_path}")

        self.dictionary_path = dictionary_path
        self.exact_map: Dict[str, Dict[str, Any]] = {}
        self.base_map: Dict[str, Dict[str, Any]] = {}
        self.ingredient_map: Dict[str, Dict[str, Any]] = {}
        self.search_names: List[str] = []
        self.name_to_record: Dict[str, Dict[str, Any]] = {}
        # Index từ khóa để tra cứu substring/prefix/suffix siêu tốc
        self.word_index: Dict[str, List[Dict[str, Any]]] = {}

        self._load_dictionary()

    def _is_valid_search_key(self, text: str) -> bool:
        if not text:
            return False
        clean = text.strip()
        if len(clean) < 3:
            return False
        if re.match(r'^(?:\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|iu|ui|%|mg\/ml|iu\/ml|meq)?|[^\w]+)$', clean, re.IGNORECASE):
            return False
        letters = re.findall(r'[a-zA-ZÀ-ỹ]', clean)
        if len(letters) < 3:
            return False
        return True

    def _index_words_for_record(self, text: str, rec: Dict[str, Any]):
        """Tách các từ khóa có nghĩa từ tên thuốc vào word_index"""
        if not text:
            return
        # Tách từ theo khoảng trắng, dấu gạch nối, dấu chấm
        tokens = re.split(r'[\s\.\-_,\(\)]+', text.lower())
        for tok in tokens:
            if len(tok) >= 3 and not tok.isdigit():
                if tok not in self.word_index:
                    self.word_index[tok] = []
                self.word_index[tok].append(rec)
                
        # Nếu là từ ghép kiểu Hãng+TênThuốc (ví dụ: Ahngookpapaze), tách các phần nếu có thể
        clean_text = text.lower()
        if "papaze" in clean_text:
            if "papaze" not in self.word_index:
                self.word_index["papaze"] = []
            self.word_index["papaze"].append(rec)

    def _is_clean_active_ingredient(self, text: str) -> bool:
        """Kiểm tra hoạt chất có phải là tên chất đơn gọn gàng, tránh câu mô tả hỗn hợp dài gây match ảo"""
        if not text or len(text) > 40:
            return False
        if len(text.split()) > 4:
            return False
        if re.search(r'(?i)\b(mỗi|chứa|tương đương|dưới dạng|tá dược|vừa đủ|tuong duong|duoi dang|ta duoc|vua du|chiet xuat|cao kho|cao dac)\b', text):
            return False
        if '(' in text or ')' in text or ':' in text:
            return False
        return True

    def _load_dictionary(self):
        with open(self.dictionary_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        self.records = records
        search_set = set()

        for rec in records:
            name = rec["name"]
            norm_name = normalize_text(name)
            self.exact_map[norm_name] = rec
            self.name_to_record[name] = rec
            if self._is_valid_search_key(name):
                search_set.add(name)

            self._index_words_for_record(name, rec)

            base = rec.get("base_name")
            if base:
                norm_base = normalize_text(base)
                if norm_base not in self.base_map:
                    self.base_map[norm_base] = rec
                if self._is_valid_search_key(base):
                    search_set.add(base)
                    self.name_to_record[base] = rec
                self._index_words_for_record(base, rec)

            ai = rec.get("active_ingredient")
            if ai:
                for part in ai.split(";"):
                    cleaned_part = part.strip()
                    cleaned_part_no_str = re.sub(r'(?i)\s*\d+(?:\.\d+)?\s*(mg|g|mcg|ml|iu|ui|%|mg\/ml|iu\/ml|meq)\b.*$', '', cleaned_part).strip()
                    
                    for candidate_ai in [cleaned_part, cleaned_part_no_str]:
                        norm_ai = normalize_text(candidate_ai)
                        if self._is_valid_search_key(candidate_ai):
                            if norm_ai not in self.ingredient_map:
                                self.ingredient_map[norm_ai] = rec
                            # Chỉ nạp vào danh sách tìm kiếm mờ nếu là tên hoạt chất ngắn gọn, không phải câu mô tả
                            if self._is_clean_active_ingredient(candidate_ai):
                                search_set.add(candidate_ai)
                                self.name_to_record[candidate_ai] = rec

        self.search_names = sorted(list(search_set))

    def match_drug_name(
        self,
        raw_query: str,
        threshold: float = 75.0
    ) -> Dict[str, Any]:
        """
        So khớp tên thuốc thông minh đa tầng.
        """
        if not raw_query:
            return {
                "matched": False,
                "drug_name": "",
                "confidence": 0.0,
                "match_type": "empty"
            }

        parsed = parse_drug_line_details(raw_query)
        clean_name = parsed["clean_name"]
        brand_no_str = parsed["brand_no_strength"]
        bracket_content = parsed["bracket_content"]
        extracted_strength = parsed["strength"]

        norm_clean = normalize_text(clean_name)
        norm_brand_no_str = normalize_text(brand_no_str)
        norm_raw = normalize_text(raw_query)

        # -------------------------------------------------------------
        # TẦNG 1: Exact Match theo tên thương mại sạch hoặc base name
        # -------------------------------------------------------------
        for query_cand, mtype in [
            (norm_clean, "exact_brand"),
            (norm_brand_no_str, "exact_brand_without_strength"),
            (norm_raw, "exact")
        ]:
            if query_cand and query_cand in self.exact_map:
                rec = self.exact_map[query_cand]
                return self._build_result(rec, 1.0, mtype, parsed)

        for query_cand, mtype in [
            (norm_clean, "base_name"),
            (norm_brand_no_str, "base_name_without_strength")
        ]:
            if query_cand and query_cand in self.base_map:
                rec = self.base_map[query_cand]
                return self._build_result(rec, 0.98, mtype, parsed)

        # -------------------------------------------------------------
        # TẦNG 2: Substring & Word-Level Match kết hợp Cross-Check Hoạt chất
        # (Giải quyết trường hợp tên thuốc viết tắt: 'papaze' -> 'Ahngookpapaze Tablet',
        # 'biocid mh' -> 'Biocid Plus')
        # -------------------------------------------------------------
        brand_words = [w for w in re.split(r'[\s\.\-_]+', norm_brand_no_str) if len(w) >= 3]
        candidate_records = []

        # Tra nhanh qua word_index
        for w in brand_words:
            if w in self.word_index:
                candidate_records.extend(self.word_index[w])

        # Quét thêm substring cho các từ ghép (như 'papaze' trong 'ahngookpapaze')
        if not candidate_records and len(norm_brand_no_str) >= 4:
            for w in brand_words:
                if len(w) >= 4:
                    for d in self.records:
                        d_name_l = d["name"].lower()
                        if w in d_name_l:
                            candidate_records.append(d)

        # Lọc unique danh sách ứng viên
        unique_cands = []
        seen_names = set()
        for c in candidate_records:
            if c["name"] not in seen_names:
                seen_names.add(c["name"])
                unique_cands.append(c)

        if unique_cands:
            best_cand = None
            best_cand_score = 0.0

            for cand in unique_cands:
                name_l = cand["name"].lower()
                base_l = cand.get("base_name", "").lower()
                ai_text = cand.get("active_ingredient", "")

                # 1. Tính điểm tên thương mại
                name_score = max(
                    fuzz.ratio(norm_brand_no_str, name_l),
                    fuzz.ratio(norm_brand_no_str, base_l),
                    fuzz.partial_ratio(norm_brand_no_str, name_l)
                )

                # 2. Tính điểm hoạt chất nếu đơn thuốc có mở ngoặc
                ai_score = 0.0
                if bracket_content:
                    ai_score = check_ingredient_match(bracket_content, ai_text)

                if bracket_content and ai_score >= 60:
                    total_score = ai_score * 0.7 + name_score * 0.3
                else:
                    total_score = name_score * 0.9

                if total_score > best_cand_score:
                    best_cand_score = total_score
                    best_cand = (cand, ai_score, name_score)

            if best_cand and best_cand_score >= 65.0:
                cand, ai_sc, name_sc = best_cand
                conf = round(best_cand_score / 100.0, 2)
                match_type = "brand_substring_cross_ingredient" if ai_sc >= 60 else "brand_substring"
                return self._build_result(cand, min(conf, 0.98), match_type, parsed)

        # -------------------------------------------------------------
        # TẦNG 3: Active Ingredient Match từ nội dung trong ngoặc (bracket_content)
        # -------------------------------------------------------------
        if bracket_content:
            norm_bracket = normalize_text(bracket_content)
            bracket_no_str = re.sub(r'(?i)\s*\d+(?:\.\d+)?\s*(mg|g|mcg|ml|iu|ui|%|mg\/ml|iu\/ml|meq)\b.*$', '', bracket_content).strip()
            norm_bracket_no_str = normalize_text(bracket_no_str)

            for cand_ai in [norm_bracket_no_str, norm_bracket]:
                if cand_ai and cand_ai in self.ingredient_map:
                    rec = self.ingredient_map[cand_ai]
                    return self._build_result(rec, 0.95, "active_ingredient_from_bracket", parsed)

            # Thử tìm theo hoạt chất có điểm trùng khớp cao nhất
            ai_candidates = []
            for d in self.records:
                sc = check_ingredient_match(bracket_content, d.get("active_ingredient", ""))
                if sc >= 75.0:
                    name_sc = fuzz.ratio(norm_brand_no_str, d["name"].lower()) if norm_brand_no_str else 50
                    ai_candidates.append((d, sc, name_sc))

            if ai_candidates:
                ai_candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
                best_d, sc, name_sc = ai_candidates[0]
                conf = round((sc * 0.6 + name_sc * 0.4) / 100.0, 2)
                return self._build_result(best_d, min(conf, 0.95), "active_ingredient_matched", parsed)

        # -------------------------------------------------------------
        # TẦNG 4: Fuzzy Match dự phòng với RapidFuzz (WRatio + default_process)
        # -------------------------------------------------------------
        candidates_to_try = []
        # Ưu tiên tìm theo tên đã lược bỏ hàm lượng trước để tránh số hàm lượng gây nhiễu
        if brand_no_str and len(brand_no_str) >= 3:
            candidates_to_try.append(brand_no_str)
        if clean_name and clean_name != brand_no_str and len(clean_name) >= 3:
            candidates_to_try.append(clean_name)

        best_result = None
        best_score = 0.0

        for cand in candidates_to_try:
            match = process.extractOne(
                cand,
                self.search_names,
                scorer=fuzz.WRatio,
                processor=utils.default_process,
                score_cutoff=threshold
            )
            if match:
                matched_str, score, _ = match
                if score > best_score:
                    best_score = score
                    best_result = (matched_str, score)

        if best_result:
            matched_str, score = best_result
            rec = self.name_to_record.get(matched_str)
            if rec:
                return self._build_result(rec, round(score / 100.0, 2), "fuzzy", parsed)

        # Không khớp được
        return {
            "matched": False,
            "drug_name": clean_name or raw_query,
            "base_name": "",
            "active_ingredient": "",
            "strength": extracted_strength,
            "dosage_form": "",
            "confidence": 0.0,
            "match_type": "none",
            "quantity": parsed.get("quantity", ""),
            "usage": parsed.get("usage", ""),
            "stt": parsed.get("stt", ""),
            "raw_query": raw_query
        }

    def _build_result(
        self,
        rec: Dict[str, Any],
        confidence: float,
        match_type: str,
        parsed: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Tạo dict kết quả đồng nhất"""
        strength = parsed.get("strength") or rec.get("strength") or ""
        return {
            "matched": True,
            "drug_name": rec["name"],
            "base_name": rec.get("base_name", ""),
            "active_ingredient": rec.get("active_ingredient", ""),
            "strength": strength,
            "dosage_form": rec.get("dosage_form", ""),
            "confidence": confidence,
            "match_type": match_type,
            "quantity": parsed.get("quantity", ""),
            "usage": parsed.get("usage", ""),
            "stt": parsed.get("stt", ""),
            "raw_query": parsed.get("raw_line", "")
        }

def match_single_drug(raw_query: str, threshold: float = 72.0) -> Dict[str, Any]:
    matcher = DrugCatalogMatcher.get_instance()
    return matcher.match_drug_name(raw_query, threshold)
