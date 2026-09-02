import os
import json
import time
import math
import requests
import threading
import random
import string
import re
from datetime import datetime
from flask import Flask
import telebot
from telebot import types

# ==========================================
# 👑 CẤU HÌNH HỆ THỐNG
# ==========================================
BOT_TOKEN = '8385677064:AAFqekWzgqj5OM67dP_AXP853KpkCYFsc8U'
ADMIN_ID = [7564889663]
ADMIN_USERNAME = "@duybmw"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ✅ MENU LỆNH
bot.set_my_commands([
    telebot.types.BotCommand("start", "🏠 Khởi động dự đoán tự động"),
    telebot.types.BotCommand("stop", "⏹️ Dừng dự đoán"),
    telebot.types.BotCommand("nhapkey", "🔑 Nhập key kích hoạt VIP"),
    telebot.types.BotCommand("taokey", "👑 [ADMIN] Tạo key VIP"),
    telebot.types.BotCommand("danhsachkey", "📋 [ADMIN] Xem danh sách key"),
    telebot.types.BotCommand("xoakey", "🗑️ [ADMIN] Xóa key"),
    telebot.types.BotCommand("lichsucau", "📊 Xem lịch sử cầu"),
    telebot.types.BotCommand("thongke", "📊 Thống kê đúng/sai"),
    telebot.types.BotCommand("admin", "👑 Bảng điều khiển admin"),
    telebot.types.BotCommand("nhapmau", "📥 Nhập file mẫu cầu"),
    telebot.types.BotCommand("xemmau", "📚 Xem danh sách mẫu cầu"),
])

# ==========================================
# 📚 PATTERN LIBRARY (LƯU TRONG FILE)
# ==========================================
PATTERNS = {}
PATTERN_FILE = "patterns.json"

def load_patterns():
    global PATTERNS
    if os.path.exists(PATTERN_FILE):
        try:
            with open(PATTERN_FILE, 'r', encoding='utf-8') as f:
                PATTERNS = json.load(f)
            print(f"✅ Đã tải {len(PATTERNS)} mẫu cầu từ file")
            return
        except:
            pass
    # Fallback: 50 mẫu cơ bản
    PATTERNS = {
        "TT": "XỈU", "TX": "TÀI", "XT": "TÀI", "XX": "XỈU",
        "TTT": "XỈU", "TTX": "TÀI", "TXT": "XỈU", "TXX": "TÀI",
        "XTT": "XỈU", "XTX": "TÀI", "XXT": "TÀI", "XXX": "XỈU",
        "TTTT": "TÀI", "TTTX": "XỈU", "TTXT": "TÀI", "TTXX": "XỈU",
        "TXTT": "XỈU", "TXTX": "TÀI", "TXXT": "XỈU", "TXXX": "TÀI",
        "XTTT": "TÀI", "XTTX": "XỈU", "XTXT": "XỈU", "XTXX": "TÀI",
        "XXTT": "XỈU", "XXTX": "TÀI", "XXXX": "TÀI",
    }
    save_patterns()
    print(f"✅ Đã tạo {len(PATTERNS)} mẫu cầu mặc định")

def save_patterns():
    with open(PATTERN_FILE, 'w', encoding='utf-8') as f:
        json.dump(PATTERNS, f, indent=2, ensure_ascii=False)

load_patterns()

# ==========================================
# 📥 LẤY DỮ LIỆU TỪ API LC79 MD5
# ==========================================
HISTORY_API_URL = "https://wtxmd52.tele68.com/v1/txmd5/lite-sessions"
user_states = {}
valid_keys = {}
authorized_users = {}
SAVE_FILE = './bot_save.json'

def init_user_state(chat_id):
    if chat_id not in user_states:
        user_states[chat_id] = {
            'history': [],
            'last_session_id': None,
            'last_sent_session': None,
            'last_sent_pred_session': None,
            'prediction': None,
            'last_prediction': None,
            'total_correct': 0,
            'total_checked': 0,
            'running': False,
            'thread': None,
        }

def save_data():
    try:
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'valid_keys': valid_keys, 'authorized_users': authorized_users}, f, indent=2)
    except Exception as e:
        print(f"Lỗi lưu: {e}")

try:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
            valid_keys = d.get('valid_keys', {})
            authorized_users = {int(k): v for k, v in d.get('authorized_users', {}).items()}
except:
    pass

def check_auth(chat_id):
    if chat_id in ADMIN_ID:
        return True
    if chat_id in authorized_users:
        if time.time() <= authorized_users[chat_id]:
            return True
        else:
            del authorized_users[chat_id]
            save_data()
    return False

def format_expire_time(ts):
    remain = ts - time.time()
    if remain <= 0: return "❌ ĐÃ HẾT HẠN"
    d = math.floor(remain / 86400)
    h = math.floor((remain % 86400) / 3600)
    m = math.floor((remain % 3600) / 60)
    if d > 0: return f"✅ CÒN {d} NGÀY {h} GIỜ {m} PHÚT"
    if h > 0: return f"✅ CÒN {h} GIỜ {m} PHÚT"
    return f"✅ CÒN {m} PHÚT"

def locked_msg():
    return f"""<pre>╔════════════════════════════════════════════╗
║    🔒 HỆ THỐNG BẢO MẬT VIP 🔒              ║
╠════════════════════════════════════════════╣
║ ⚠️ TÀI KHOẢN CHƯA KÍCH HOẠT BẢN QUYỀN VIP ║
║ 🔑 MỞ KHÓA → {ADMIN_USERNAME}
║ 💡 /nhapkey MÃ_KEY                          ║
╚════════════════════════════════════════════╝</pre>"""

def fetch_history(limit=30):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://lc79b.bet",
            "Referer": "https://lc79b.bet/"
        }
        r = requests.get(HISTORY_API_URL, headers=headers, timeout=15)
        lst = r.json().get('list', [])
        if not lst: return []
        lst = list(reversed(lst))[-limit:]
        parsed = []
        for p in lst:
            res_raw = p.get('resultTruyenThong')
            sess = p.get('session') or p.get('id')
            res = 'TÀI' if res_raw == 'TAI' else ('XỈU' if res_raw == 'XIU' else None)
            if res and sess:
                parsed.append({'session': int(sess), 'result': res})
        return parsed
    except Exception as e:
        print(f"Lỗi API: {e}")
        return []

# ==========================================
# 🧠 THUẬT TOÁN 16 ENSEMBLE
# ==========================================
def clamp(v, lo, hi): return max(lo, min(hi, v))
def safeDiv(a, b, d=0.5): return d if b == 0 else a / b
def round4(x): return round(x, 4)

def getResults(history, n):
    return [h['result'] for h in history[:min(n, len(history))] if h.get('result')]

def countTai(results): return results.count('TÀI')

def currentStreak(results):
    if not results: return {'type': None, 'len': 0}
    t = results[0]; length = 1
    for i in range(1, len(results)):
        if results[i] == t: length += 1
        else: break
    return {'type': t, 'len': length}

def transitionCounts(results):
    TT = TX = XT = XX = 0
    for i in range(len(results) - 1):
        older = results[i + 1]; newer = results[i]
        if older == 'TÀI' and newer == 'TÀI': TT += 1
        elif older == 'TÀI' and newer == 'XỈU': TX += 1
        elif older == 'XỈU' and newer == 'TÀI': XT += 1
        elif older == 'XỈU' and newer == 'XỈU': XX += 1
    return {'TT': TT, 'TX': TX, 'XT': XT, 'XX': XX}

def shannonEntropy(results):
    if len(results) < 2: return 1.0
    p = countTai(results) / len(results)
    if p <= 0 or p >= 1: return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

def bayesianTaiProb(results, alpha=1, beta=1):
    t = countTai(results); n = len(results)
    return (t + alpha) / (n + alpha + beta)

def analyzeCau(history):
    res = getResults(history, 30)
    if len(res) < 3:
        return {'type': 'UNKNOWN', 'strength': 0, 'pTai': 0.5, 'label': 'Chưa đủ cầu'}
    st = currentStreak(res)
    trans = transitionCounts(res)
    switches = trans['TX'] + trans['XT']
    ratio = countTai(res) / len(res)
    ent = shannonEntropy(res)

    if st['len'] >= 3:
        cont = total = 0
        for i in range(len(res) - st['len']):
            ok = True
            for k in range(st['len']):
                if res[i + k] != st['type']: ok = False; break
            if ok and (i + st['len'] < len(res)):
                total += 1
                if res[i + st['len']] == st['type']: cont += 1
        pCont = cont / total if total >= 2 else (0.4 if st['len'] >= 5 else 0.52)
        pCont = clamp(pCont, 0.22, 0.78)
        pTai = pCont if st['type'] == 'TÀI' else (1 - pCont)
        return {'type': 'CAU_BET_T' if st['type'] == 'TÀI' else 'CAU_BET_X', 'strength': clamp(st['len'] / 8, 0.3, 1), 'pTai': pTai, 'label': f"Cầu bệt {st['type']} x{st['len']}", 'streak': st}

    if switches >= max(2, len(res) - 2) * 0.85 and len(res) >= 4:
        pTai = 0 if res[0] == 'TÀI' else 1
        soft = 0.5 + (pTai - 0.5) * 0.7
        return {'type': 'CAU_1_1', 'strength': 0.65, 'pTai': soft, 'label': 'Cầu 1-1 (xen kẽ)'}

    if len(res) >= 6:
        pairs = []
        for i in range(0, min(6, len(res) - 1), 2):
            if res[i] == res[i + 1]: pairs.append(res[i])
        if len(pairs) >= 2 and pairs[0] != pairs[1]:
            lastPairType = res[0] if res[0] == res[1] else None
            if lastPairType:
                pTai = (0.62 if st['len'] == 1 else 0.38) if lastPairType == 'TÀI' else (0.38 if st['len'] == 1 else 0.62)
                return {'type': 'CAU_2_2', 'strength': 0.55, 'pTai': pTai, 'label': 'Cầu 2-2'}

    if ratio >= 0.68:
        return {'type': 'CAU_NGHIENG_T', 'strength': clamp((ratio - 0.5) * 2, 0.3, 0.9), 'pTai': clamp(0.5 + (ratio - 0.5) * 0.8, 0.55, 0.78), 'label': 'Cầu nghiêng Tài'}
    if ratio <= 0.32:
        return {'type': 'CAU_NGHIENG_X', 'strength': clamp((0.5 - ratio) * 2, 0.3, 0.9), 'pTai': clamp(0.5 - (0.5 - ratio) * 0.8, 0.22, 0.45), 'label': 'Cầu nghiêng Xỉu'}
    if ent > 0.95:
        return {'type': 'CAU_HON_HOP', 'strength': 0.2, 'pTai': 0.5, 'label': 'Cầu hỗn hợp'}
    return {'type': 'CAU_THUONG', 'strength': 0.35, 'pTai': clamp(0.5 + (ratio - 0.5) * 0.6, 0.35, 0.65), 'label': 'Cầu thường'}

def analyzePreviousResults(history):
    res = getResults(history, 20)
    if not res: return {'pTai': 0.5, 'conf': 0.2, 'signals': []}
    signals = []; score = 0.0; weightSum = 0.0
    for w in [3, 5, 8, 12, 20]:
        if len(res) >= min(w, 3):
            slice_res = res[:min(w, len(res))]
            p = bayesianTaiProb(slice_res, 1, 1)
            wgt = math.sqrt(len(slice_res)) * (1.3 if w <= 5 else 1.0)
            score += (p - 0.5) * wgt; weightSum += wgt
            signals.append({'name': f'freq_{w}', 'pTai': p})
    if len(res) >= 3:
        last3 = "".join(res[:3]); t = n = 0
        for i in range(len(res) - 3):
            if "".join(res[i + 1:i + 4]) == last3:
                n += 1
                if res[i] == 'TÀI': t += 1
        if n >= 2:
            p = (t + 1) / (n + 2)
            score += (p - 0.5) * (2 + n * 0.3); weightSum += 2 + n * 0.3
            signals.append({'name': 'last3_match', 'pTai': p, 'n': n})
    pTai = clamp(0.5 + score / weightSum, 0.18, 0.82) if weightSum > 0 else 0.5
    conf = clamp(0.3 + min(len(res) / 20, 1) * 0.4 + abs(pTai - 0.5), 0.25, 0.85)
    return {'pTai': pTai, 'conf': conf, 'signals': signals, 'sample': len(res)}

def detectRegime(history):
    res = getResults(history, 20)
    if len(res) < 5: return 'COLD_START'
    st = currentStreak(res); ent = shannonEntropy(res)
    trans = transitionCounts(res); switches = trans['TX'] + trans['XT']
    ratio = countTai(res) / len(res)
    if st['len'] >= 5: return 'STREAK_T' if st['type'] == 'TÀI' else 'STREAK_X'
    if switches >= len(res) * 0.7: return 'ALTERNATING'
    if ent < 0.6 and ratio > 0.65: return 'STABLE_T'
    if ent < 0.6 and ratio < 0.35: return 'STABLE_X'
    if ent > 0.95: return 'HIGH_ENTROPY'
    if abs(ratio - 0.5) < 0.12: return 'BALANCED'
    return 'TRENDING'

# ----- 15 SUB-MODELS -----
def modelFrequency(history, window):
    res = getResults(history, window)
    if not res: return None
    pTai = bayesianTaiProb(res, 1, 1)
    shrink = min(1.0, len(res) / 8.0)
    adj = 0.5 + (pTai - 0.5) * shrink
    return {'id': f'freq_{window}', 'pTai': adj, 'sample': len(res), 'conf': clamp(0.35 + len(res) * 0.03, 0.35, 0.82)}

def modelExpFreq(history):
    res = getResults(history, 30)
    if not res: return None
    wTai = wTotal = 0.0; w = 1.0
    for r in res:
        if r == 'TÀI': wTai += w
        wTotal += w; w *= 0.88
    return {'id': 'exp_freq', 'pTai': safeDiv(wTai, wTotal), 'sample': len(res), 'conf': clamp(0.4 + len(res) * 0.025, 0.4, 0.85)}

def modelStreak(history):
    res = getResults(history, 40)
    if len(res) < 2: return None
    st = currentStreak(res); cont = total = 0
    for i in range(len(res) - st['len']):
        same = True
        for k in range(st['len']):
            if res[i + k] != st['type']: same = False; break
        if same and (i + st['len'] < len(res)):
            total += 1
            if res[i + st['len']] == st['type']: cont += 1
    pContinue = cont / total if total > 0 else (0.42 if st['len'] >= 4 else 0.55)
    pContinue = clamp(pContinue, 0.25, 0.75)
    pTai = pContinue if st['type'] == 'TÀI' else (1.0 - pContinue)
    return {'id': 'streak', 'pTai': pTai, 'sample': total or len(res), 'conf': clamp(0.4 + min(st['len'], 6) * 0.05, 0.4, 0.8)}

def modelMarkov1(history):
    res = getResults(history, 60)
    if len(res) < 3: return None
    c = transitionCounts(res)
    fromT = c['TT'] + c['TX']; fromX = c['XT'] + c['XX']
    last = res[0]
    pTai = safeDiv(c['TT'], fromT) if last == 'TÀI' else safeDiv(c['XT'], fromX)
    s = fromT if last == 'TÀI' else fromX
    return {'id': 'markov1', 'pTai': clamp(pTai, 0.15, 0.85), 'sample': s, 'conf': clamp(0.45 + s * 0.02, 0.45, 0.88)}

def modelMarkov2(history):
    res = getResults(history, 60)
    if len(res) < 5: return None
    counts = {}
    for i in range(len(res) - 2):
        key = f"{res[i + 2]}|{res[i + 1]}"
        if key not in counts: counts[key] = {'T': 0, 'X': 0}
        if res[i] == 'TÀI': counts[key]['T'] += 1
        else: counts[key]['X'] += 1
    key = f"{res[1]}|{res[0]}"
    c = counts.get(key, {'T': 1, 'X': 1})
    return {'id': 'markov2', 'pTai': safeDiv(c['T'] + 1, c['T'] + c['X'] + 2), 'sample': c['T'] + c['X'], 'conf': clamp(0.4 + (c['T'] + c['X']) * 0.03, 0.4, 0.85)}

def modelNgram(history):
    res = getResults(history, 50)
    if len(res) < 4: return None
    last2 = res[1] + res[0]
    last3 = (res[2] if len(res) > 2 else '') + res[1] + res[0]
    t2 = n2 = t3 = n3 = 0
    for i in range(len(res) - 2):
        if res[i + 2] + res[i + 1] == last2:
            n2 += 1
            if res[i] == 'TÀI': t2 += 1
    for i in range(len(res) - 3):
        if res[i + 3] + res[i + 2] + res[i + 1] == last3:
            n3 += 1
            if res[i] == 'TÀI': t3 += 1
    if n3 >= 2: pTai = (t3 + 1) / (n3 + 2); sample = n3
    elif n2 >= 2: pTai = (t2 + 1) / (n2 + 2); sample = n2
    else: return None
    return {'id': 'ngram', 'pTai': pTai, 'sample': sample, 'conf': clamp(0.38 + sample * 0.04, 0.38, 0.8)}

def modelMomentum(history):
    res = getResults(history, 15)
    if len(res) < 3: return None
    score = 0.0; sumW = 0.0; w = 1.0
    for r in res:
        score += (1 if r == 'TÀI' else -1) * w
        sumW += w; w *= 0.75
    pTai = clamp(0.5 + (score / sumW) * 0.28, 0.22, 0.78)
    return {'id': 'momentum', 'pTai': pTai, 'sample': len(res), 'conf': 0.55}

def modelPattern10(history):
    res = getResults(history, 10)
    if len(res) < 4: return None
    tCount = countTai(res); ratio = tCount / len(res)
    st = currentStreak(res); ent = shannonEntropy(res)
    trans = transitionCounts(res); switches = trans['TX'] + trans['XT']
    bias = (ratio - 0.5) * 0.9
    if st['len'] >= 4: bias += (-0.12 if st['type'] == 'TÀI' else 0.12)
    if switches >= len(res) - 2: bias *= 0.6
    damp = 1.0 - min(ent, 1.0) * 0.35
    pTai = clamp(0.5 + bias * damp, 0.2, 0.8)
    return {
        'id': 'pattern10', 'pTai': pTai, 'sample': len(res),
        'conf': clamp(0.5 + (10 - abs(tCount - 5)) * 0.03 - ent * 0.15, 0.35, 0.78),
        'meta': {'tCount': tCount, 'ratio': round4(ratio), 'streak': st, 'entropy': round4(ent), 'switches': switches}
    }

def modelCau(history):
    cau = analyzeCau(history)
    return {'id': 'cau_engine', 'pTai': cau['pTai'], 'sample': len(getResults(history, 30)), 'conf': clamp(0.4 + cau['strength'] * 0.4, 0.35, 0.85), 'meta': cau}

def modelPrevAnalysis(history):
    a = analyzePreviousResults(history)
    return {'id': 'prev_analysis', 'pTai': a['pTai'], 'sample': a.get('sample', 0), 'conf': a['conf'], 'meta': a}

def modelBayesianGlobal(history):
    res = getResults(history, 100)
    if not res: return None
    return {'id': 'bayes_global', 'pTai': bayesianTaiProb(res, 2, 2), 'sample': len(res), 'conf': clamp(0.4 + math.log2(1 + len(res)) * 0.08, 0.4, 0.75)}

def modelSimilarity(history):
    res = getResults(history, 80)
    if len(res) < 12: return None
    patternLen = min(5, math.floor(len(res) / 4.0))
    target = "".join(res[:patternLen])
    tNext = nNext = 0
    for i in range(patternLen, len(res) - 1):
        if "".join(res[i:i + patternLen]) == target:
            nNext += 1
            if res[i - 1] == 'TÀI': tNext += 1
    if nNext < 2: return None
    return {'id': 'similarity', 'pTai': (tNext + 1) / (nNext + 2), 'sample': nNext, 'conf': clamp(0.42 + nNext * 0.05, 0.42, 0.82)}

def modelPatternLibrary(history):
    if len(history) < 3:
        return None
    res = getResults(history, 10)
    if len(res) < 3:
        return None
    for n in range(min(10, len(res)), 2, -1):
        pattern = "".join(res[:n])
        if pattern in PATTERNS:
            pred = PATTERNS[pattern]
            pTai = 0.95 if pred == 'TÀI' else 0.05
            return {
                'id': 'pattern_library',
                'pTai': pTai,
                'sample': len(PATTERNS),
                'conf': min(75 + n * 2, 94),
                'meta': {'matched': pattern, 'length': n, 'pred': pred}
            }
    return None

def getModelWeight(modelId, baseConf, sample):
    return clamp(baseConf * (0.5 + sample / 20), 0.3, 2.0)

def runEnsemble(history):
    models = []
    n = len(history)
    candidates = [
        lambda: modelFrequency(history, 5),
        lambda: modelFrequency(history, 10),
        lambda: modelFrequency(history, 20) if n >= 15 else None,
        lambda: modelFrequency(history, 50) if n >= 30 else None,
        lambda: modelExpFreq(history),
        lambda: modelStreak(history),
        lambda: modelMarkov1(history),
        lambda: modelMarkov2(history) if n >= 12 else None,
        lambda: modelNgram(history),
        lambda: modelMomentum(history),
        lambda: modelPattern10(history),
        lambda: modelCau(history),
        lambda: modelPrevAnalysis(history),
        lambda: modelBayesianGlobal(history),
        lambda: modelSimilarity(history),
        lambda: modelPatternLibrary(history),
    ]
    for fn in candidates:
        try:
            m = fn()
            if m and isinstance(m.get('pTai'), (int, float)) and not math.isnan(m['pTai']):
                m['pTai'] = clamp(m['pTai'], 0.12, 0.88)
                models.append(m)
        except: pass
    if not models:
        return {'prediction': 'TÀI', 'tai_probability': 0.5, 'xiu_probability': 0.5, 'confidence': 0.2, 'risk': 'VERY_HIGH', 'sample_size': n, 'regime': 'COLD_START', 'model_count': 0, 'models_agree': 0, 'top_models': [], 'analysis': {'note': 'Prior 50/50'}, 'models': []}
    sumW = sumP = 0.0
    weighted = []
    for m in models:
        w = getModelWeight(m['id'], m.get('conf', 0.5), m.get('sample', 1))
        sumW += w; sumP += m['pTai'] * w
        m_copy = dict(m); m_copy['weight'] = w; weighted.append(m_copy)
    pTai = clamp(sumP / sumW, 0.18, 0.82) if sumW > 0 else 0.5
    predT = len([m for m in weighted if m['pTai'] >= 0.5])
    agree = max(predT, len(models) - predT)
    agreeRatio = agree / len(models)
    regime = detectRegime(history)
    ent = shannonEntropy(getResults(history, 15))
    cau = analyzeCau(history)
    gap = abs(pTai - 0.5) * 2
    conf = clamp(0.25 + gap * 0.35 + agreeRatio * 0.25 + min(n / 40, 1) * 0.15 - ent * 0.12, 0.15, 0.88)
    if regime in ['HIGH_ENTROPY', 'COLD_START']: conf *= 0.7
    if n < 5: conf *= 0.55
    elif n < 10: conf *= 0.75
    conf = clamp(conf, 0.15, 0.88)
    risk = 'MEDIUM'
    if conf < 0.35 or n < 4: risk = 'VERY_HIGH'
    elif conf < 0.48: risk = 'HIGH'
    elif conf > 0.68 and gap > 0.22: risk = 'LOW'
    prediction = 'TÀI' if pTai >= 0.5 else 'XỈU'
    top = sorted(weighted, key=lambda x: x['weight'], reverse=True)[:5]
    top_models = [{'id': m['id'], 'pTai': round4(m['pTai']), 'w': round4(m['weight'])} for m in top]
    p10 = modelPattern10(history)
    return {
        'prediction': prediction,
        'tai_probability': round4(pTai),
        'xiu_probability': round4(1 - pTai),
        'confidence': round4(conf),
        'risk': risk,
        'sample_size': n,
        'regime': regime,
        'model_count': len(models),
        'models_agree': agree,
        'top_models': top_models,
        'pattern10': p10['meta'] if p10 else {},
        'cau': cau,
        'analysis': {'entropy': round4(ent), 'streak': currentStreak(getResults(history, 30)), 'freq10': round4(countTai(getResults(history, 10)) / min(10, n)) if n >= 5 else None, 'cauLabel': cau['label']},
        'models': weighted
    }

def format_prediction(pred_result, session_id):
    pred = pred_result['prediction']
    conf = int(pred_result['confidence'] * 100)
    tai_pct = int(pred_result['tai_probability'] * 100)
    xiu_pct = int(pred_result['xiu_probability'] * 100)
    cau_label = pred_result.get('cau', {}).get('label', 'Chưa xác định')
    risk = pred_result.get('risk', 'MEDIUM')
    model_count = pred_result.get('model_count', 0)
    icon = '🔵' if pred == 'TÀI' else '🔴'
    
    msg = f"""<pre>╔════════════════════════════════════════════╗
║      📊 DỰ ĐOÁN PHIÊN #{session_id}              ║
╠════════════════════════════════════════════╣
║ 🎯 DỰ ĐOÁN: {icon} {pred}
║ 📊 ĐỘ TIN CẬY: {conf}% (Rủi ro: {risk})
║ 🧬 MẪU CẦU: {cau_label}
║ 📈 XÁC SUẤT: TÀI [{tai_pct}%] - XỈU [{xiu_pct}%]
║ 🧠 SỐ MÔ HÌNH DÙNG: {model_count}
╚════════════════════════════════════════════╝</pre>"""
    return msg

def format_result(actual, predicted, session_id):
    correct = (actual == predicted)
    icon = '✅' if correct else '❌'
    status = 'ĐÚNG' if correct else 'SAI'
    actual_icon = '🔵' if actual == 'TÀI' else '🔴'
    pred_icon = '🔵' if predicted == 'TÀI' else '🔴'
    
    msg = f"""<pre>╔════════════════════════════════════════════╗
║      🎲 KẾT QUẢ PHIÊN #{session_id}              ║
╠════════════════════════════════════════════╣
║ 📌 KẾT QUẢ THỰC TẾ: {actual_icon} {actual}
║ 🤖 DỰ ĐOÁN: {pred_icon} {predicted}
║ 📊 ĐÁNH GIÁ: {icon} {status}
╚════════════════════════════════════════════╝</pre>"""
    return msg

# ==========================================
# 🤖 VÒNG LẶP TỰ ĐỘNG
# ==========================================
def prediction_loop(chat_id):
    init_user_state(chat_id)
    st = user_states[chat_id]
    st['running'] = True
    
    while st['running']:
        try:
            history = fetch_history(20)
            if not history:
                time.sleep(5)
                continue
            
            st['history'] = history
            last_session = history[0]['session'] if history else None
            last_result = history[0]['result'] if history else None
            
            if st.get('last_prediction') and last_result:
                pred_session = st['last_prediction'].get('session')
                pred_value = st['last_prediction'].get('prediction')
                
                if pred_session == last_session and pred_value and st.get('last_sent_session') != last_session:
                    result_msg = format_result(last_result, pred_value, last_session)
                    try:
                        bot.send_message(chat_id, result_msg, parse_mode='HTML')
                        st['last_sent_session'] = last_session
                    except:
                        pass
                    
                    if pred_value == last_result:
                        st['total_correct'] += 1
                    st['total_checked'] += 1
            
            if history:
                next_session = last_session + 1 if last_session else 1
                
                if st.get('last_sent_pred_session') != next_session:
                    pred_result = runEnsemble(history)
                    st['prediction'] = pred_result
                    st['last_prediction'] = {
                        'session': next_session,
                        'prediction': pred_result['prediction']
                    }
                    
                    pred_msg = format_prediction(pred_result, next_session)
                    try:
                        bot.send_message(chat_id, pred_msg, parse_mode='HTML')
                        st['last_sent_pred_session'] = next_session
                    except:
                        pass
            
            time.sleep(5)
            
        except Exception as e:
            print(f"Lỗi vòng lặp: {e}")
            time.sleep(5)

# ==========================================
# 📥 NHẬN FILE MẪU CẦU
# ==========================================
@bot.message_handler(commands=['nhapmau'])
def nhapmau_command(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    bot.reply_to(message, "📤 Vui lòng gửi file **.txt** chứa mẫu cầu.\n\n"
                          "Định dạng file:\n"
                          "<code>\"TXXT\":\"Tài\"</code>\n"
                          "<code>\"XTTX\":\"Xỉu\"</code>\n\n"
                          "Bot sẽ đọc và cập nhật Pattern Library.",
                          parse_mode='HTML')

@bot.message_handler(content_types=['document'])
def handle_pattern_file(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    if not file_name.lower().endswith('.txt'):
        bot.reply_to(message, "❌ Chỉ hỗ trợ file **.txt**!")
        return
    
    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        content = downloaded.decode('utf-8')
        
        global PATTERNS
        matches = re.findall(r'"([TX]+)":"([TàiXỉu]+)"', content)
        
        if not matches:
            matches = re.findall(r'([TX]+)\s*[:=]\s*([TàiXỉu]+)', content)
        
        if not matches:
            bot.reply_to(message, "❌ Không tìm thấy mẫu cầu hợp lệ trong file.\n"
                                  "Định dạng đúng: <code>\"TXXT\":\"Tài\"</code>",
                                  parse_mode='HTML')
            return
        
        count = 0
        for pattern, result in matches:
            if 'Tài' in result or result == 'T':
                PATTERNS[pattern] = 'TÀI'
            else:
                PATTERNS[pattern] = 'XỈU'
            count += 1
        
        save_patterns()
        
        bot.reply_to(message, f"✅ **ĐÃ CẬP NHẬT {count} MẪU CẦU!**\n"
                              f"📚 Tổng mẫu hiện có: {len(PATTERNS)}\n"
                              f"🔑 Đã lưu vào file {PATTERN_FILE}",
                              parse_mode='HTML')
        
        sample = list(PATTERNS.items())[:5]
        sample_text = "\n".join([f"<code>{k}</code> → {v}" for k, v in sample])
        bot.send_message(chat_id, f"📋 Mẫu đầu tiên:\n{sample_text}\n...", parse_mode='HTML')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý file: {str(e)}")

@bot.message_handler(commands=['xemmau'])
def xemmau_command(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    total = len(PATTERNS)
    if total == 0:
        bot.reply_to(message, "📭 Chưa có mẫu cầu nào.")
        return
    
    sample = list(PATTERNS.items())[:20]
    text = f"📚 **TỔNG MẪU CẦU: {total}**\n\n"
    for k, v in sample:
        text += f"<code>{k}</code> → {v}\n"
    
    if total > 20:
        text += f"\n... và {total - 20} mẫu khác."
    
    bot.reply_to(message, text, parse_mode='HTML')

# ==========================================
# 🔑 LỆNH NHẬP KEY
# ==========================================
@bot.message_handler(commands=['nhapkey'])
def send_nhapkey(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, '✅ Hướng dẫn: /nhapkey VIP-XXXX')
        return
        
    k = parts[1].strip().upper()
    if k in valid_keys:
        d = valid_keys[k]
        authorized_users[message.chat.id] = time.time() + d * 86400
        del valid_keys[k]
        save_data()
        bot.reply_to(message, f"🎉 KÍCH HOẠT THÀNH CÔNG GÓI VIP {d} NGÀY ✅")
    else:
        bot.reply_to(message, f"❌ KEY KHÔNG HỢP LỆ HOẶC ĐÃ ĐƯỢC SỬ DỤNG\n📩 MUA TẠI: {ADMIN_USERNAME}")

# ==========================================
# 🔑 LỆNH TẠO KEY (ADMIN)
# ==========================================
@bot.message_handler(commands=['taokey'])
def send_taokey(message):
    if message.chat.id not in ADMIN_ID:
        return bot.reply_to(message, '⛔ Chỉ admin mới có quyền tạo key')
    
    parts = message.text.split()
    n = 30
    if len(parts) > 1 and parts[1].isdigit():
        n = int(parts[1])
        
    if n <= 0:
        return bot.reply_to(message, '✅ Hướng dẫn: /taokey 7 / 30 / 90')
        
    key = 'VIP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    valid_keys[key] = n
    save_data()
    
    het = datetime.fromtimestamp(time.time() + n * 86400).strftime('%d/%m/%Y %H:%M:%S')
    msg = f"✅ TẠO KEY VIP THÀNH CÔNG:\n🔑 <code>{key}</code>\n⏳ Thời hạn: {n} NGÀY\n📅 Hết hạn: {het}\n📊 TỔNG KEY CHƯA DÙNG: {len(valid_keys)}"
    bot.reply_to(message, msg, parse_mode='HTML')

# ==========================================
# 📋 LỆNH XEM DANH SÁCH KEY (ADMIN)
# ==========================================
@bot.message_handler(commands=['danhsachkey'])
def send_danhsachkey(message):
    if message.chat.id not in ADMIN_ID:
        return bot.reply_to(message, '⛔ Chỉ admin')
    if not valid_keys:
        return bot.reply_to(message, '📭 Danh sách key kho trống')
        
    lines = [f"<code>{k}</code> → {v} NGÀY" for k, v in valid_keys.items()]
    msg = "\n".join(lines) + f"\n\n📊 TỔNG CỘNG KHỎ: {len(valid_keys)} KEY VIP"
    bot.reply_to(message, msg, parse_mode='HTML')

# ==========================================
# 🗑️ LỆNH XÓA KEY (ADMIN)
# ==========================================
@bot.message_handler(commands=['xoakey'])
def send_xoakey(message):
    if message.chat.id not in ADMIN_ID:
        return bot.reply_to(message, '⛔ Chỉ admin')
    
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, '✅ Hướng dẫn: /xoakey VIP-XXXX')
    
    k = parts[1].strip().upper()
    if k in valid_keys:
        del valid_keys[k]
        save_data()
        bot.reply_to(message, f"🗑️ ĐÃ XÓA KEY: <code>{k}</code>", parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ KHÔNG TÌM THẤY KEY: <code>{k}</code>", parse_mode='HTML')

# ==========================================
# 🔑 LỆNH BOT
# ==========================================
@bot.message_handler(commands=['start'])
def send_start(message):
    chat_id = message.chat.id
    init_user_state(chat_id)
    
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    if not user_states[chat_id].get('running'):
        thread = threading.Thread(target=prediction_loop, args=(chat_id,), daemon=True)
        thread.start()
        user_states[chat_id]['thread'] = thread
        bot.reply_to(message, "✅ ĐÃ BẬT DỰ ĐOÁN TỰ ĐỘNG!\nFetch API 5s, gửi khi có phiên mới.")
    else:
        bot.reply_to(message, "⏳ Dự đoán tự động đang chạy!")

@bot.message_handler(commands=['stop'])
def send_stop(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    if chat_id in user_states:
        user_states[chat_id]['running'] = False
        bot.reply_to(message, "⏹️ ĐÃ DỪNG DỰ ĐOÁN TỰ ĐỘNG.")
    else:
        bot.reply_to(message, "⚠️ Chưa có tiến trình nào đang chạy.")

@bot.message_handler(commands=['lichsucau'])
def send_lichsucau(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    init_user_state(chat_id)
    history = fetch_history(20)
    if not history:
        bot.reply_to(message, "📭 Chưa có dữ liệu")
        return
    
    results = [h['result'] for h in history[:20]]
    tai = results.count('TÀI')
    xiu = results.count('XỈU')
    icons = "".join(['🔵' if r == 'TÀI' else '🔴' for r in results])
    
    msg = f"""📊 20 PHIÊN GẦN NHẤT:
🔵 TÀI: {tai} | 🔴 XỈU: {xiu}

{icons}"""
    bot.reply_to(message, msg)

@bot.message_handler(commands=['thongke'])
def send_thongke(message):
    chat_id = message.chat.id
    if not check_auth(chat_id):
        bot.reply_to(message, locked_msg())
        return
    
    init_user_state(chat_id)
    st = user_states[chat_id]
    
    total = st['total_checked']
    correct = st['total_correct']
    wrong = total - correct
    rate = round(correct / total * 100, 1) if total > 0 else 0
    
    msg = f"""📊 THỐNG KÊ ĐÚNG/SAI:
✅ ĐÚNG: {correct}
❌ SAI: {wrong}
📦 TỔNG: {total}
🎯 TỈ LỆ: {rate}%"""
    bot.reply_to(message, msg)

# ==========================================
# 👑 LỆNH ADMIN
# ==========================================
@bot.message_handler(commands=['admin'])
def send_admin(message):
    chat_id = message.chat.id
    if chat_id not in ADMIN_ID:
        bot.reply_to(message, "⛔ Bạn không có quyền admin!")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔑 Tạo Key", callback_data="admin_taokey"),
        types.InlineKeyboardButton("📋 Danh sách Key", callback_data="admin_listkey"),
        types.InlineKeyboardButton("📊 Thống kê bot", callback_data="admin_stats"),
        types.InlineKeyboardButton("🔄 Reset thống kê", callback_data="admin_reset"),
    )
    
    bot.reply_to(message, "👑 **BẢNG ĐIỀU KHIỂN ADMIN**", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    if call.from_user.id not in ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Không có quyền!")
        return
    
    action = call.data.split('_')[1]
    
    if action == 'taokey':
        bot.send_message(call.message.chat.id, "📝 Nhập số ngày cho Key (VD: 30):")
        bot.register_next_step_handler(call.message, process_taokey)
    
    elif action == 'listkey':
        if not valid_keys:
            bot.edit_message_text("📭 Chưa có key nào.", call.message.chat.id, call.message.message_id)
            return
        lines = [f"<code>{k}</code> → {v} ngày" for k, v in valid_keys.items()]
        msg = "📋 **DANH SÁCH KEY:**\n\n" + "\n".join(lines)
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode='HTML')
    
    elif action == 'stats':
        total_users = len(user_states)
        total_pred = sum(st.get('total_checked', 0) for st in user_states.values())
        total_correct = sum(st.get('total_correct', 0) for st in user_states.values())
        rate = round(total_correct / total_pred * 100, 1) if total_pred > 0 else 0
        
        msg = f"""📊 **THỐNG KÊ TOÀN HỆ THỐNG:**
👤 Số user: {total_users}
📦 Tổng dự đoán: {total_pred}
✅ Đúng: {total_correct}
🎯 Tỉ lệ: {rate}%
🔑 Key còn: {len(valid_keys)}"""
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode='HTML')
    
    elif action == 'reset':
        for st in user_states.values():
            st['total_correct'] = 0
            st['total_checked'] = 0
        bot.edit_message_text("✅ Đã reset thống kê!", call.message.chat.id, call.message.message_id)

def process_taokey(message):
    try:
        days = int(message.text.strip())
        if days <= 0:
            bot.reply_to(message, "⚠️ Số ngày phải > 0")
            return
        
        key = 'VIP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        valid_keys[key] = days
        save_data()
        
        het = datetime.fromtimestamp(time.time() + days * 86400).strftime('%d/%m/%Y %H:%M:%S')
        msg = f"""✅ **TẠO KEY THÀNH CÔNG!**
🔑 Key: <code>{key}</code>
⏳ Hạn: {days} ngày
📅 Hết hạn: {het}"""
        bot.reply_to(message, msg, parse_mode='HTML')
    except ValueError:
        bot.reply_to(message, "⚠️ Vui lòng nhập số ngày hợp lệ!")

# ==========================================
# 🚀 FLASK - GIỮ BOT CHẠY
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return f"🤖 LC79 PREDICTOR PRO ĐANG CHẠY! {int(time.time())}"

def run_flask():
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==========================================
# 🚀 CHẠY BOT
# ==========================================
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("🤖 LC79 PREDICTOR PRO ĐANG CHẠY...")
    print(f"📚 Pattern Library: {len(PATTERNS)} mẫu cầu")
    print(f"👑 Admin IDs: {ADMIN_ID}")
    print(f"🔗 API: {HISTORY_API_URL}")
    bot.infinity_polling()
