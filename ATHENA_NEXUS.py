# -*- coding: utf-8 -*-
"""ATHENA NEXUS — jogos de tabuleiro, cartas e bilhar num único ficheiro.

Instalação:
    python -m pip install pygame numpy

Executar:
    python ATHENA_NEXUS.py

O microfone, a voz e a ligação opcional ao Ollama podem ser usados quando
as respetivas dependências estiverem instaladas. Os jogos funcionam sem eles.
"""



# ========================================================================
# COMUM — código integrado
# ========================================================================


"""Perfil guardado em disco, livro de experiência e elementos de interface comuns aos jogos."""
import hashlib
import json
import os
import threading
import time

import numpy as np

comum_W, comum_H = 1360, 765
comum_HERE = os.path.dirname(os.path.abspath(__file__))
comum_PERFIL = os.path.join(comum_HERE, "ia_pesos.npz")
comum_P = None
comum_LOCK = threading.RLock()
comum_CACHE = {"sig": None, "arrays": {}}


# Ganchos da ATHENA (o NEXUS substitui-os; quando um jogo corre sozinho ficam inertes)
comum_athena_brain = None


def comum_athena_record_move(jogo, quem, jogada):
    pass


def comum_athena_nova_partida(jogo):
    pass


def comum_athena_ativo(jogo):
    return False


def comum_athena_vies(jogo, candidatos, estado=None):
    return None


def comum_athena_escolha(jogo, candidato, estado=None):
    pass


# Perfil persistente (guardado dentro de ia_pesos.npz, ao lado dos pesos neuronais)
def comum_assinatura():
    try:
        st = os.stat(comum_PERFIL)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def comum_copiar_ilegivel():
    try:
        destino = comum_PERFIL + ".ilegivel"
        if os.path.exists(comum_PERFIL) and not os.path.exists(destino):
            import shutil
            shutil.copy2(comum_PERFIL, destino)
            print("[ATHENA perfil] Ficheiro ilegível; cópia de segurança em", destino)
    except Exception:
        pass


def comum_arrays_em_disco():
    sig = comum_assinatura()
    if sig is None:
        return {}
    if comum_CACHE["sig"] != sig:
        try:
            with np.load(comum_PERFIL, allow_pickle=False) as data:
                comum_CACHE["arrays"] = {k: data[k] for k in data.files if k != "ATHENA_PROFILE"}
            comum_CACHE["sig"] = sig
        except Exception as exc:
            print("[ATHENA perfil] Não foi possível ler os pesos:", repr(exc))
            comum_copiar_ilegivel()
            return dict(comum_CACHE["arrays"])
    return comum_CACHE["arrays"]


def comum_escrever_npz(caminho, arrays, comprimir=False):
    tmp = caminho + ".tmp.npz"
    (np.savez_compressed if comprimir else np.savez)(tmp, **arrays)
    for tentativa in range(6):
        try:
            os.replace(tmp, caminho)
            return
        except PermissionError:
            time.sleep(0.15 * (tentativa + 1))
    os.replace(tmp, caminho)


def comum_perfil():
    global comum_P
    with comum_LOCK:
        if comum_P is None:
            comum_P = {}
            if os.path.exists(comum_PERFIL):
                try:
                    with np.load(comum_PERFIL, allow_pickle=False) as data:
                        raw = str(data["ATHENA_PROFILE"].item()) if "ATHENA_PROFILE" in data.files else "{}"
                    carregado = json.loads(raw)
                    if isinstance(carregado, dict):
                        comum_P = carregado
                except Exception as exc:
                    print("[ATHENA perfil] Perfil ilegível, a recomeçar vazio:", repr(exc))
                    comum_copiar_ilegivel()
                    comum_P = {}
        return comum_P


def comum_guardar():
    with comum_LOCK:
        try:
            arrays = dict(comum_arrays_em_disco())
            arrays["ATHENA_PROFILE"] = np.asarray(json.dumps(comum_perfil(), ensure_ascii=False, separators=(",", ":")))
            comum_escrever_npz(comum_PERFIL, arrays)
            comum_CACHE["sig"] = comum_assinatura()
            comum_CACHE["arrays"] = {k: v for k, v in arrays.items() if k != "ATHENA_PROFILE"}
            return True
        except Exception as exc:
            print("[ATHENA perfil] ERRO ao guardar o progresso:", repr(exc))
            return False


def comum_secao(nome, defeito):
    with comum_LOCK:
        s = comum_perfil().setdefault(nome, {})
        for k, v in defeito.items():
            s.setdefault(k, json.loads(json.dumps(v)))
        return s


def comum_registar_resultado(jogo, nivel, resultado):
    st = comum_secao("stats", {})
    r = st.setdefault(jogo, {}).setdefault(nivel, {"v": 0, "d": 0, "e": 0})
    r[resultado] = r.get(resultado, 0) + 1
    comum_guardar()


def comum_reset_perfil():
    global comum_P
    with comum_LOCK:
        comum_P = {}
    comum_guardar()


# Livro de experiência (xadrez, damas, quatro em linha)
def comum_chave(obj):
    if not isinstance(obj, (bytes, bytearray)):
        obj = repr(obj).encode()
    return hashlib.md5(obj).hexdigest()[:12]


class comum_Experiencia:
    MAX = 30000

    def __init__(self, nome):
        self.d = comum_secao("exp", {}).setdefault(nome, {})
        self.nome = nome

    def valor(self, pos_key, mv):
        return self.d.get(pos_key, {}).get(mv, 0.0)

    def tem(self, pos_key):
        return pos_key in self.d

    def registar(self, lances, resultado):
        if resultado == 0:
            resultado = -0.25          # empate: ligeiramente mau (queremos ganhar)
        peso = 1.0
        for pk, mv in reversed(lances[-70:]):
            slot = self.d.setdefault(pk, {})
            v = slot.get(mv, 0.0) + resultado * peso * (1.0 if resultado < 0 else 0.5)
            slot[mv] = max(-3.0, min(2.0, v))
            peso *= 0.82
        while len(self.d) > self.MAX:
            self.d.pop(next(iter(self.d)))
        comum_guardar()


# Interface (pygame importado só quando é preciso)
comum_BG = (22, 29, 39)
comum_BG2 = (34, 45, 57)
comum_TXT = (244, 241, 232)
comum_DIM = (174, 183, 190)
comum_OURO = (244, 190, 92)
comum_VERDE = (70, 190, 110)
comum_VERM = (220, 80, 80)

comum_fonts = {}


def comum_fonte(size, bold=True):
    import pygame
    k = (size, bold)
    if k not in comum_fonts:
        comum_fonts[k] = pygame.font.SysFont("arial", size, bold=bold)
    return comum_fonts[k]


def comum_texto(surf, s, pos, size=20, cor=comum_TXT, ancora="topleft", bold=True):
    img = comum_fonte(size, bold).render(str(s), True, cor)
    r = img.get_rect()
    setattr(r, ancora, pos)
    surf.blit(img, r)
    return r


def comum_abrir_ecra(fullscreen=True):
    import pygame
    pygame.init()
    flags = (pygame.FULLSCREEN | pygame.SCALED) if fullscreen else 0
    try:
        return pygame.display.set_mode((comum_W, comum_H), flags)
    except pygame.error:
        return pygame.display.set_mode((comum_W, comum_H))


def comum_fundo(screen):
    import pygame
    screen.fill(comum_BG)
    pygame.draw.rect(screen, comum_BG2, (0, 0, comum_W, 64))


def comum_botao(screen, rect, label, ativo=False, hover=False, cor=None, size=20):
    import pygame
    base = cor or ((70, 96, 150) if ativo else (52, 56, 72))
    if hover:
        base = tuple(min(255, c + 22) for c in base)
    pygame.draw.rect(screen, base, rect, border_radius=10)
    if ativo:
        pygame.draw.rect(screen, comum_OURO, rect, 2, border_radius=10)
    comum_texto(screen, label, rect.center, size, comum_TXT, "center")


def comum_escolher(screen, clock, titulo, opcoes, descr=None, sub=None, inicial=0, cheatcode=None):
    """Menu simples: teclado e rato funcionam da mesma forma."""
    import pygame

    if not opcoes:
        return None

    sel = max(0, min(len(opcoes) - 1, int(inicial or 0)))
    sequencia = ""
    n = len(opcoes)
    bw = min(760, comum_W - 100)
    gap = 12
    bh = min(58, max(38, (470 - (n - 1) * gap) // n))
    total = n * bh + (n - 1) * gap
    y0 = max(145, (comum_H - total) // 2 - 12)
    rects = [
        pygame.Rect((comum_W - bw) // 2, y0 + i * (bh + gap), bw, bh)
        for i in range(n)
    ]

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                    except pygame.error:
                        pass
                    continue
                if cheatcode and e.unicode and e.unicode.isprintable():
                    sequencia = (sequencia + e.unicode.upper())[-len(cheatcode):]
                    if sequencia == cheatcode.upper():
                        return "cheat"
                if e.key == pygame.K_ESCAPE:
                    return None
                if e.key in (pygame.K_UP, pygame.K_LEFT):
                    sel = (sel - 1) % n
                elif e.key in (pygame.K_DOWN, pygame.K_RIGHT):
                    sel = (sel + 1) % n
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return sel
            elif e.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(rects):
                    if rect.collidepoint(e.pos):
                        sel = i
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, rect in enumerate(rects):
                    if rect.collidepoint(e.pos):
                        return i

        comum_fundo(screen)
        pygame.draw.circle(screen, (42, 65, 77), (105, 105), 54, 2)
        pygame.draw.circle(screen, (42, 65, 77), (comum_W - 105, comum_H - 110), 78, 2)
        comum_texto(screen, "ESCOLHE O QUE TE APETECE JOGAR", (comum_W // 2, 66),
                     14, comum_OURO, "center", False)
        comum_texto(screen, titulo, (comum_W // 2, 101), 29, comum_TXT, "center")
        if sub:
            comum_texto(screen, sub, (comum_W // 2, 132), 16, comum_DIM, "center", False)

        for i, rect in enumerate(rects):
            ativo = i == sel
            base = (63, 91, 99) if ativo else (43, 55, 67)
            if ativo:
                base = tuple(min(255, c + 10) for c in base)
            pygame.draw.rect(screen, base, rect, border_radius=13)
            if ativo:
                pygame.draw.rect(screen, comum_OURO, rect, 2, border_radius=13)
                pygame.draw.circle(screen, comum_OURO, (rect.left + 25, rect.centery), 5)
            comum_texto(screen, opcoes[i], (rect.centerx + (8 if ativo else 0), rect.centery),
                         19, comum_TXT, "center", True)

        if descr and sel < len(descr) and descr[sel]:
            comum_texto(screen, descr[sel], (comum_W // 2, min(rects[-1].bottom + 38, comum_H - 58)),
                         16, comum_DIM, "center", False)
        comum_texto(screen, "Setas para escolher · Enter para confirmar · Esc para voltar",
                     (comum_W // 2, comum_H - 25), 13, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(60)


def comum_mostrar_msg(screen, clock, linhas, esperar=True):
    import pygame
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                try:
                    pygame.display.toggle_fullscreen()
                except pygame.error:
                    pass
                continue
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                return None
        comum_fundo(screen)
        y = 120
        for i, l in enumerate(linhas):
            comum_texto(screen, l, (comum_W // 2, y), 26 if i == 0 else 18, comum_TXT if i == 0 else comum_DIM, "center", i == 0)
            y += 46 if i == 0 else 30
        comum_texto(screen, "clica ou prime uma tecla", (comum_W // 2, comum_H - 26), 14, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(60)


def comum_tempo():
    return time.time()



# ========================================================================
# QUATRO — código integrado
# ========================================================================


"""Quatro em Linha."""
import math
import random
import threading
import time


quatro_HH = 6
quatro_H1 = 7
quatro_BOARD = sum(((1 << quatro_HH) - 1) << (c * quatro_H1) for c in range(7))
quatro_BOTTOM = sum(1 << (c * quatro_H1) for c in range(7))
quatro_COLMASK = [((1 << quatro_HH) - 1) << (c * quatro_H1) for c in range(7)]
quatro_ORDER = [3, 2, 4, 1, 5, 0, 6]
quatro_ODD = sum(1 << (c * quatro_H1 + r) for c in range(7) for r in (0, 2, 4))     # linhas 1,3,5 (a contar de 1)
quatro_EVEN = sum(1 << (c * quatro_H1 + r) for c in range(7) for r in (1, 3, 5))
quatro_WIN = 10000
quatro_INF = 10 ** 9
quatro_pc = int.bit_count if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))

quatro_NIVEIS = {   # tempo (s), profundidade máxima, probabilidade de jogada aleatória
    "facil": (0.0, 2, 0.30), "normal": (0.0, 4, 0.0), "dificil": (1.5, 30, 0.0),
    "mestre": (4.0, 30, 0.0), "absurdo": (9.0, 42, 0.0),
}


def quatro_alinhado(p):
    m = p & (p >> quatro_H1)
    if m & (m >> (2 * quatro_H1)):
        return True
    m = p & (p >> quatro_HH)
    if m & (m >> (2 * quatro_HH)):
        return True
    m = p & (p >> (quatro_HH + 2))
    if m & (m >> (2 * (quatro_HH + 2))):
        return True
    m = p & (p >> 1)
    return bool(m & (m >> 2))


def quatro_winning(p, mask):
    r = (p << 1) & (p << 2) & (p << 3)
    for s in (quatro_H1, quatro_HH, quatro_HH + 2):
        t = (p << s) & (p << 2 * s)
        r |= t & (p << 3 * s)
        r |= t & (p >> s)
        t = (p >> s) & (p >> 2 * s)
        r |= t & (p << s)
        r |= t & (p >> 3 * s)
    return r & (quatro_BOARD ^ mask)


class quatro_Timeout(Exception):
    pass


class quatro_Motor:
    def __init__(self):
        self.tt = {}
        self.nodes = 0
        self.deadline = None

    def _heur(self, pos, mask, n, mine, ow):
        first = (n % 2 == 0)
        pm, po = (quatro_ODD, quatro_EVEN) if first else (quatro_EVEN, quatro_ODD)
        opp = pos ^ mask
        h = 6 * (quatro_pc(mine) - quatro_pc(ow)) + 10 * (quatro_pc(mine & pm) - quatro_pc(ow & po))
        h += 3 * (quatro_pc(pos & quatro_COLMASK[3]) - quatro_pc(opp & quatro_COLMASK[3]))
        h += 2 * (quatro_pc(pos & (quatro_COLMASK[2] | quatro_COLMASK[4])) - quatro_pc(opp & (quatro_COLMASK[2] | quatro_COLMASK[4])))
        return h

    def neg(self, pos, mask, n, depth, a, b):
        self.nodes += 1
        if self.deadline is not None and (self.nodes & 2047) == 0 and time.time() > self.deadline:
            raise quatro_Timeout
        if n >= 42:
            return 0
        possible = (mask + quatro_BOTTOM) & quatro_BOARD
        mine = quatro_winning(pos, mask)
        if mine & possible:
            return quatro_WIN - n - 1
        ow = quatro_winning(pos ^ mask, mask)
        forced = ow & possible
        if forced:
            if forced & (forced - 1):
                return -(quatro_WIN - n - 2)
            possible = forced
        possible &= ~(ow >> 1)
        if not possible:
            return -(quatro_WIN - n - 2)
        if depth <= 0:
            return self._heur(pos, mask, n, mine, ow)
        key = pos + mask
        ent = self.tt.get(key)
        a0 = a
        if ent is not None:
            d, fl, v = ent
            if d >= depth:
                if fl == 0:
                    return v
                if fl == 1 and v > a:
                    a = v
                elif fl == 2 and v < b:
                    b = v
                if a >= b:
                    return v
        moves = []
        for c in quatro_ORDER:
            mv = possible & quatro_COLMASK[c]
            if mv:
                moves.append((quatro_pc(quatro_winning(pos | mv, mask | mv)) * 8 - abs(c - 3), mv))
        moves.sort(key=lambda z: -z[0])
        best = -quatro_INF
        opp = pos ^ mask
        for _, mv in moves:
            v = -self.neg(opp, mask | mv, n + 1, depth - 1, -b, -a)
            if v > best:
                best = v
                if v > a:
                    a = v
                    if a >= b:
                        break
        if len(self.tt) > 1_500_000:
            self.tt.clear()
        self.tt[key] = (depth, 0 if a0 < best < b else (1 if best >= b else 2), best)
        return best

    def _raiz(self, pos, mask, n, depth, cols, full=False):
        res = []
        alpha = -quatro_INF
        opp = pos ^ mask
        for c in cols:
            mv = ((mask + quatro_BOTTOM) & quatro_BOARD) & quatro_COLMASK[c]
            if quatro_winning(pos, mask) & mv:
                v = quatro_WIN - n - 1
            else:
                v = -self.neg(opp, mask | mv, n + 1, depth - 1, -quatro_INF, quatro_INF if full else -alpha)
            res.append((v, c))
            if v > alpha and not full:
                alpha = v
        return res

    def elegir(self, pos, mask, n, tempo=2.0, prof=42, exp=None, aleatorio=0.0, info=None):
        possible = (mask + quatro_BOTTOM) & quatro_BOARD
        legais = [c for c in quatro_ORDER if possible & quatro_COLMASK[c]]
        if len(legais) == 1:
            return legais[0], 0, 0
        if n == 0:
            return 3, 0, 0
        if aleatorio and random.random() < aleatorio:
            return random.choice(legais), 0, 0
        self.nodes = 0
        self.deadline = (time.time() + tempo) if tempo else None
        cols = list(legais)
        best_c, best_v, depth_done = legais[0], 0, 0
        try:
            for d in range(1, prof + 1):
                res = self._raiz(pos, mask, n, d, cols)
                res.sort(key=lambda z: -z[0])
                best_v, best_c = res[0]
                cols = [c for _, c in res]            # a melhor primeiro na próxima iteração
                depth_done = d
                if info:
                    info(d, best_v)
                if abs(best_v) > quatro_WIN - 100:
                    break
                if n + d >= 42:
                    break
        except quatro_Timeout:
            pass
        key = comum_chave((pos, mask))
        usar_rede = comum_athena_ativo("quatro")
        if ((exp is not None and exp.tem(key)) or usar_rede) and abs(best_v) < quatro_WIN - 100:
            try:
                self.deadline = time.time() + max(0.5, tempo * 0.3)
                res = self._raiz(pos, mask, n, max(1, depth_done - 1), legais, full=True)
                vies = comum_athena_vies("quatro", [c for _, c in res], (pos, mask, n)) if usar_rede else None
                sc = {}
                for i, (v, c) in enumerate(res):
                    sc[c] = (v + (150 * max(-1.0, min(0.5, exp.valor(key, str(c)))) if exp is not None else 0.0)
                             + (60.0 * vies[i] if vies else 0.0))
                best_c = max(sc, key=sc.get)
            except quatro_Timeout:
                pass
        self.deadline = None
        comum_athena_escolha("quatro", best_c, (pos, mask, n))
        return best_c, best_v, depth_done


def quatro_jogar_col(pos, mask, c):
    mv = ((mask + quatro_BOTTOM) & quatro_BOARD) & quatro_COLMASK[c]
    return pos ^ mask, mask | mv, mv


# Interface
def quatro_jogar(screen, clock, nivel="absurdo", quem_comeca=None):
    import pygame
    exp = comum_Experiencia("quatro")
    motor = quatro_Motor()
    c0 = quem_comeca if quem_comeca is not None else comum_escolher(
        screen, clock, "Quatro em Linha", ["Eu começo", "A IA começa"],
        ["Tu jogas primeiro (vermelho)", "A IA joga primeiro (amarelo) - bem mais difícil"],
        f"Nível da IA: {nivel}")
    if c0 in (None, "quit"):
        return c0
    humano_comeca = (c0 == 0)
    CS, BX, BY = 88, 70, 110
    tempo_n, prof_n, alea_n = quatro_NIVEIS[nivel]

    while True:
        motor = quatro_Motor()                             # motor novo: uma pesquisa antiga nunca interfere com a nova
        comum_athena_nova_partida("quatro")
        # estado: p1 = jogador que começa
        stones = {0: 0, 1: 0}                       # 0 = quem começou, 1 = o outro
        mask = 0
        n = 0
        hum = 0 if humano_comeca else 1             # índice (0/1) do humano
        lances_ia = quatro_Lances()
        win_cells = None
        resultado = None
        anim = None
        box = {"res": None, "busy": False}
        msg = "A tua vez - clica numa coluna" if humano_comeca else ""
        hover = 3
        info = {"d": 0, "v": 0}

        def vez():
            return n % 2

        def pos_atual():
            return stones[vez()]

        def colocar(c):
            nonlocal mask, n, win_cells, resultado
            comum_athena_record_move("quatro", "jogador" if vez() == hum else "ATHENA", f"coluna {c + 1}")
            r = None
            p = pos_atual()
            mv = ((mask + quatro_BOTTOM) & quatro_BOARD) & quatro_COLMASK[c]
            stones[vez()] = p | mv
            mask |= mv
            n += 1
            if quatro_alinhado(stones[(n - 1) % 2]):
                resultado = (n - 1) % 2
                win_cells = quatro_celulas_vencedoras(stones[resultado])
            elif n >= 42:
                resultado = -1

        def altura(c):
            return quatro_pc(mask & quatro_COLMASK[c])

        def pensar():
            box["busy"] = True
            p, m, nn = pos_atual(), mask, n

            def inf(d, v):
                info["d"], info["v"] = d, v

            def work():
                c, v, d = motor.elegir(p, m, nn, tempo_n, prof_n, exp, alea_n, inf)
                box["res"] = (c, v, d, comum_chave((p, m)))
            threading.Thread(target=work, daemon=True).start()

        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    quatro_fim(resultado, hum, lances_ia, exp, nivel)
                    return "quit"
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        try:
                            pygame.display.toggle_fullscreen()
                        except pygame.error:
                            pass
                        continue
                    if e.key == pygame.K_ESCAPE:
                        return "menu"
                    if resultado is not None and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        quatro_fim(resultado, hum, lances_ia, exp, nivel)
                        return quatro_veredito(resultado, hum)
                    if e.key == pygame.K_r:
                        if resultado is None and n > 0 and not lances_ia.registado:
                            lances_ia.registado = True                       # desistir conta como derrota
                            comum_registar_resultado("quatro", nivel, "d")
                        running = False
                    if pygame.K_1 <= e.key <= pygame.K_7 and resultado is None and vez() == hum and anim is None:
                        c = e.key - pygame.K_1
                        if altura(c) < 6:
                            anim = {"c": c, "r": altura(c), "y": float(BY - CS), "vy": 0.0, "who": hum}
                if e.type == pygame.MOUSEMOTION:
                    hover = max(0, min(6, (e.pos[0] - BX) // CS))
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and resultado is not None:
                    quatro_fim(resultado, hum, lances_ia, exp, nivel)
                    return quatro_veredito(resultado, hum)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and resultado is None \
                        and vez() == hum and anim is None:
                    c = (e.pos[0] - BX) // CS
                    if 0 <= c < 7 and BY - 40 < e.pos[1] < BY + 6 * CS and altura(c) < 6:
                        anim = {"c": c, "r": altura(c), "y": float(BY - CS), "vy": 0.0, "who": hum}
            # IA
            if resultado is None and vez() != hum and anim is None:
                if not box["busy"]:
                    pensar()
                    msg = "A IA está a pensar..."
                elif box["res"] is not None:
                    c, v, d, k = box["res"]
                    box["res"], box["busy"] = None, False
                    lances_ia.append((k, str(c)))
                    anim = {"c": c, "r": altura(c), "y": float(BY - CS), "vy": 0.0, "who": 1 - hum}
            # animação da queda
            if anim is not None:
                anim["vy"] += 2.2
                anim["y"] += anim["vy"]
                alvo = BY + (5 - anim["r"]) * CS
                if anim["y"] >= alvo:
                    colocar(anim["c"])
                    anim = None
                    if resultado is None:
                        msg = "A tua vez - clica numa coluna" if vez() == hum else ""
                    else:
                        msg = ("Ganhaste!" if resultado == hum else "Empate" if resultado == -1 else "A IA ganhou")
                        quatro_fim(resultado, hum, lances_ia, exp, nivel)
            # desenho
            comum_fundo(screen)
            comum_texto(screen, "Quatro em Linha", (quatro_W_C, 32), 28, comum_TXT, "center")
            pygame.draw.rect(screen, (30, 70, 170), (BX - 12, BY - 10, 7 * CS + 24, 6 * CS + 22), border_radius=16)
            for c in range(7):
                for r in range(6):
                    cx, cy = BX + c * CS + CS // 2, BY + (5 - r) * CS + CS // 2
                    bit = 1 << (c * quatro_H1 + r)
                    if stones[0] & bit:
                        col = (225, 50, 50) if hum == 0 else (245, 205, 40)
                    elif stones[1] & bit:
                        col = (225, 50, 50) if hum == 1 else (245, 205, 40)
                    else:
                        col = (14, 18, 30)
                    pygame.draw.circle(screen, col, (cx, cy), CS // 2 - 8)
                    if col != (14, 18, 30):
                        pygame.draw.circle(screen, tuple(max(0, x - 50) for x in col), (cx, cy), CS // 2 - 8, 3)
            if win_cells:
                for c, r in win_cells:
                    pygame.draw.circle(screen, (255, 255, 255), (BX + c * CS + CS // 2, BY + (5 - r) * CS + CS // 2),
                                       CS // 2 - 4, 4)
            cor_h = (225, 50, 50)
            cor_ia = (245, 205, 40)
            if anim is not None:
                col = cor_h if anim["who"] == hum else cor_ia
                pygame.draw.circle(screen, col, (BX + anim["c"] * CS + CS // 2, int(anim["y"]) + CS // 2), CS // 2 - 8)
            elif resultado is None and vez() == hum:
                pygame.draw.circle(screen, cor_h, (BX + hover * CS + CS // 2, BY - 38), CS // 2 - 20)
            # painel
            px = BX + 7 * CS + 60
            comum_texto(screen, f"Nível: {nivel}", (px, 130), 22)
            comum_texto(screen, "Tu: vermelho", (px, 175), 18, cor_h)
            comum_texto(screen, "IA: amarelo", (px, 205), 18, cor_ia)
            if info["d"] and resultado is None and vez() != hum:
                comum_texto(screen, f"profundidade {info['d']}", (px, 260), 16, comum_DIM, bold=False)
            comum_texto(screen, f"Experiência guardada: {len(exp.d)} posições", (px, 300), 15, comum_DIM, bold=False)
            comum_texto(screen, "R = nova partida   ESC = menu", (px, 340), 15, comum_DIM, bold=False)
            comum_texto(screen, "teclas 1-7 também jogam", (px, 365), 15, comum_DIM, bold=False)
            comum_texto(screen, msg, (BX, 672), 22, comum_OURO)
            pygame.display.flip()
            clock.tick(60)


quatro_W_C = comum_W // 2


def quatro_celulas_vencedoras(p):
    out = set()
    for c in range(7):
        for r in range(6):
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                cells = [(c + k * dc, r + k * dr) for k in range(4)]
                if all(0 <= a < 7 and 0 <= b < 6 and p >> (a * quatro_H1 + b) & 1 for a, b in cells):
                    out.update(cells)
    return sorted(out)


class quatro_Lances(list):
    registado = False


def quatro_fim(resultado, hum, lances_ia, exp, nivel):
    if resultado is None or lances_ia.registado:
        return
    lances_ia.registado = True
    if resultado == -1:
        comum_registar_resultado("quatro", nivel, "e")
        exp.registar(lances_ia, 0)
    elif resultado == hum:
        comum_registar_resultado("quatro", nivel, "v")
        exp.registar(lances_ia, -1)
    else:
        comum_registar_resultado("quatro", nivel, "d")
        exp.registar(lances_ia, +1)


def quatro_veredito(resultado, hum):
    if resultado == -1:
        return "draw"
    return "win" if resultado == hum else "loss"



# ========================================================================
# DAMAS — código integrado
# ========================================================================


"""Damas."""
import random
import threading
import time


damas_DIRS = [(1, -1), (1, 1), (-1, -1), (-1, 1)]
damas_RAYS = []
for _sq in range(64):
    _r, _f = divmod(_sq, 8)
    _rays = []
    for _dr, _df in damas_DIRS:
        _l, _rr, _ff = [], _r + _dr, _f + _df
        while 0 <= _rr < 8 and 0 <= _ff < 8:
            _l.append(_rr * 8 + _ff)
            _rr += _dr
            _ff += _df
        _rays.append(_l)
    damas_RAYS.append(_rays)
damas_DARK = [(s // 8 + s % 8) % 2 == 0 for s in range(64)]
damas_CENTER = [0] * 64
for _s in range(64):
    _r, _f = divmod(_s, 8)
    damas_CENTER[_s] = int(3 - max(abs(_r - 3.5), abs(_f - 3.5)))      # 0..3
damas_WIN = 100000
damas_INF = 10 ** 9
damas_NIVEIS = {"facil": (0.0, 2, 0.25), "normal": (0.0, 4, 0.0), "dificil": (1.5, 30, 0.0),
          "mestre": (4.0, 30, 0.0), "absurdo": (9.0, 40, 0.0)}


def damas_inicial():
    b = [0] * 64
    for s in range(64):
        if damas_DARK[s]:
            r = s // 8
            if r < 3:
                b[s] = 1
            elif r > 4:
                b[s] = -1
    return b


def damas_caps(b, origin, cur, king, side, cap, out):
    found = False
    for ray in damas_RAYS[cur]:
        if not king:
            if len(ray) >= 2:
                v = ray[0]
                if b[v] * side < 0 and v not in cap and b[ray[1]] == 0:
                    found = True
                    damas_caps(b, origin, ray[1], king, side, cap + (v,), out)
        else:
            i, n = 0, len(ray)
            while i < n and b[ray[i]] == 0:
                i += 1
            if i < n and b[ray[i]] * side < 0 and ray[i] not in cap:
                v = ray[i]
                j = i + 1
                while j < n and b[ray[j]] == 0:
                    found = True
                    damas_caps(b, origin, ray[j], king, side, cap + (v,), out)
                    j += 1
    if not found and cap:
        out.append((origin, cur, cap))


def damas_gerar(b, side):
    caps = []
    for sq in range(64):
        p = b[sq]
        if p * side > 0:
            b[sq] = 0
            damas_caps(b, sq, sq, abs(p) == 2, side, (), caps)
            b[sq] = p
    if caps:
        mx = max(len(m[2]) for m in caps)
        return [m for m in caps if len(m[2]) == mx], True
    out = []
    for sq in range(64):
        p = b[sq]
        if p * side <= 0:
            continue
        if abs(p) == 2:
            for ray in damas_RAYS[sq]:
                for t in ray:
                    if b[t]:
                        break
                    out.append((sq, t, ()))
        else:
            for ray in (damas_RAYS[sq][0:2] if side == 1 else damas_RAYS[sq][2:4]):
                if ray and b[ray[0]] == 0:
                    out.append((sq, ray[0], ()))
    return out, False


def damas_aplicar(b, side, m):
    fr, to, caps = m
    nb = b[:]
    p = nb[fr]
    nb[fr] = 0
    for c in caps:
        nb[c] = 0
    if abs(p) == 1 and ((side == 1 and to // 8 == 7) or (side == -1 and to // 8 == 0)):
        p = 2 * side
    nb[to] = p
    return nb


def damas_avaliar(b):
    s = 0
    for sq in range(64):
        p = b[sq]
        if not p:
            continue
        r, f = divmod(sq, 8)
        edge = 3 if (f == 0 or f == 7) else 0
        if p == 1:
            s += 100 + 4 * r + damas_CENTER[sq] * 2 + edge + (8 if r == 0 else 0)
        elif p == -1:
            s -= 100 + 4 * (7 - r) + damas_CENTER[sq] * 2 + edge + (8 if r == 7 else 0)
        elif p == 2:
            s += 340 + damas_CENTER[sq] * 3
        else:
            s -= 340 + damas_CENTER[sq] * 3
    return s


class damas_Timeout(Exception):
    pass


class damas_Motor:
    def __init__(self):
        self.tt = {}
        self.nodes = 0
        self.deadline = None
        self.hist = {}

    def neg(self, b, side, depth, a, bt, ply):
        self.nodes += 1
        if self.deadline is not None and (self.nodes & 1023) == 0 and time.time() > self.deadline:
            raise damas_Timeout
        mv, cap = damas_gerar(b, side)
        if not mv:
            return -damas_WIN + ply
        if depth <= 0 and not (cap and ply < 40):
            return damas_avaliar(b) * side
        if depth <= 0:
            depth = 1
        key = (tuple(b), side)
        ent = self.tt.get(key)
        a0 = a
        tmove = None
        if ent is not None:
            d, fl, v, tmove = ent
            if d >= depth:
                if fl == 0:
                    return v
                if fl == 1 and v > a:
                    a = v
                elif fl == 2 and v < bt:
                    bt = v
                if a >= bt:
                    return v
        if len(mv) > 1:
            hist = self.hist
            mv.sort(key=lambda m: (m == tmove, len(m[2]), hist.get((m[0], m[1]), 0)), reverse=True)
        best, bm = -damas_INF, None
        for m in mv:
            v = -self.neg(damas_aplicar(b, side, m), -side, depth - 1, -bt, -a, ply + 1)
            if v > best:
                best, bm = v, m
                if v > a:
                    a = v
                    if a >= bt:
                        if not m[2]:
                            self.hist[(m[0], m[1])] = self.hist.get((m[0], m[1]), 0) + depth * depth
                        break
        if len(self.tt) > 800_000:
            self.tt.clear()
        self.tt[key] = (depth, 0 if a0 < best < bt else (1 if best >= bt else 2), best, bm)
        return best

    def _raiz(self, b, side, depth, moves, full=False):
        res, alpha = [], -damas_INF
        for m in moves:
            v = -self.neg(damas_aplicar(b, side, m), -side, depth - 1, -damas_INF, damas_INF if full else -alpha, 1)
            res.append((v, m))
            if v > alpha and not full:
                alpha = v
        return res

    def elegir(self, b, side, tempo=2.0, prof=30, exp=None, aleatorio=0.0, info=None):
        moves, _ = damas_gerar(b, side)
        if len(moves) <= 1:
            return (moves[0] if moves else None), 0, 0
        if aleatorio and random.random() < aleatorio:
            return random.choice(moves), 0, 0
        self.nodes = 0
        self.deadline = (time.time() + tempo) if tempo else None
        order = list(moves)
        random.shuffle(order)
        best_m, best_v, done = order[0], 0, 0
        try:
            for d in range(1, prof + 1):
                res = self._raiz(b, side, d, order)
                res.sort(key=lambda z: -z[0])
                best_v, best_m = res[0]
                order = [m for _, m in res]
                done = d
                if info:
                    info(d, best_v)
                if abs(best_v) > damas_WIN - 100:
                    break
        except damas_Timeout:
            pass
        key = comum_chave((tuple(b), side))
        usar_rede = comum_athena_ativo("damas")
        if ((exp is not None and exp.tem(key)) or usar_rede) and abs(best_v) < damas_WIN - 100:
            try:
                self.deadline = time.time() + max(0.5, tempo * 0.3)
                res = self._raiz(b, side, max(1, done - 1), moves, full=True)
                vies = comum_athena_vies("damas", [m for _, m in res], (tuple(b), side)) if usar_rede else None
                sc = {}
                for i, (v, m) in enumerate(res):
                    sc[m] = (v + (80 * max(-1.0, min(0.5, exp.valor(key, damas_str_mov(m)))) if exp is not None else 0.0)
                             + (40.0 * vies[i] if vies else 0.0))
                best_m = max(sc, key=sc.get)
            except damas_Timeout:
                pass
        self.deadline = None
        comum_athena_escolha("damas", best_m, (tuple(b), side))
        return best_m, best_v, done


def damas_str_mov(m):
    return f"{m[0]}>{m[1]}:{','.join(map(str, m[2]))}"


def damas_nome_casa(s):
    return "abcdefgh"[s % 8] + str(s // 8 + 1)


# Interface
class damas_Lances(list):
    registado = False


def damas_jogar(screen, clock, nivel="absurdo", quem_comeca=None):
    import pygame
    exp = comum_Experiencia("damas")
    motor = damas_Motor()
    c0 = quem_comeca if quem_comeca is not None else comum_escolher(
        screen, clock, "Damas", ["Jogo com as brancas (começo)", "Jogo com as pretas"],
        ["Tu começas com as brancas", "A ATHENA começa com as brancas"], f"Nível da IA: {nivel}")
    if c0 in (None, "quit"):
        return c0
    hum_side = 1 if c0 == 0 else -1
    tempo_n, prof_n, alea_n = damas_NIVEIS[nivel]
    SQ, BX, BY = 76, 70, 70
    flip = (hum_side == -1)

    def xy(s):
        r, f = divmod(s, 8)
        if flip:
            return BX + (7 - f) * SQ, BY + r * SQ
        return BX + f * SQ, BY + (7 - r) * SQ

    def casa_em(pos):
        c, rr = (pos[0] - BX) // SQ, (pos[1] - BY) // SQ
        if not (0 <= c < 8 and 0 <= rr < 8):
            return None
        return (rr * 8 + (7 - c)) if flip else ((7 - rr) * 8 + c)

    while True:
        motor = damas_Motor()                             # motor novo: uma pesquisa antiga nunca interfere com a nova
        comum_athena_nova_partida("damas")
        b = damas_inicial()
        side = 1
        sel = None
        last = None
        resultado = None          # +1 brancas, -1 pretas, 0 empate
        quiet = 0
        vistos = {}
        lances = damas_Lances()
        box = {"res": None, "busy": False}
        info = {"d": 0, "v": 0}
        msg = ""
        moves, forced = damas_gerar(b, side)
        running = True

        def fim_jogo(res):
            nonlocal resultado, msg
            resultado = res
            if res == 0:
                msg = "Empate"
                comum_registar_resultado("damas", nivel, "e")
                exp.registar(lances, 0)
            elif res == hum_side:
                msg = "Ganhaste!"
                comum_registar_resultado("damas", nivel, "v")
                exp.registar(lances, -1)
            else:
                msg = "A IA ganhou"
                comum_registar_resultado("damas", nivel, "d")
                exp.registar(lances, +1)
            lances.registado = True

        def jogar_mov(m):
            nonlocal b, side, last, moves, forced, quiet, sel, msg
            comum_athena_record_move("damas", "jogador" if side == hum_side else "ATHENA",
                                     f"{damas_nome_casa(m[0])} -> {damas_nome_casa(m[1])}" + (" (captura)" if m[2] else ""))
            p = b[m[0]]
            if m[2] or abs(p) == 1:
                quiet = 0
            else:
                quiet += 1
            b = damas_aplicar(b, side, m)
            last = (m[0], m[1])
            side = -side
            sel = None
            k = (tuple(b), side)
            vistos[k] = vistos.get(k, 0) + 1
            moves, forced = damas_gerar(b, side)
            if not moves:
                fim_jogo(-side)
            elif vistos[k] >= 3:
                fim_jogo(0)
            elif quiet >= 40:
                fim_jogo(0)
            else:
                msg = ""

        def pensar():
            box["busy"] = True
            bb, ss = b[:], side

            def inf(d, v):
                info["d"], info["v"] = d, v

            def work():
                m, v, d = motor.elegir(bb, ss, tempo_n, prof_n, exp, alea_n, inf)
                box["res"] = (m, comum_chave((tuple(bb), ss)))
            threading.Thread(target=work, daemon=True).start()

        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    if resultado is None and lances and not lances.registado:
                        pass
                    return "quit"
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        try:
                            pygame.display.toggle_fullscreen()
                        except pygame.error:
                            pass
                        continue
                    if e.key == pygame.K_ESCAPE:
                        return "menu"
                    if resultado is not None and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return damas_veredito(resultado, hum_side)
                    if e.key == pygame.K_r:
                        if resultado is None and lances and not lances.registado:
                            lances.registado = True
                            comum_registar_resultado("damas", nivel, "d")
                        running = False
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and resultado is not None:
                    return damas_veredito(resultado, hum_side)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and resultado is None and side == hum_side:
                    s = casa_em(e.pos)
                    if s is None:
                        continue
                    dest = [m for m in moves if m[0] == sel and m[1] == s]
                    if dest:
                        jogar_mov(dest[0])
                    elif b[s] * side > 0 and any(m[0] == s for m in moves):
                        sel = s
                    else:
                        sel = None
                        if forced:
                            msg = "Captura obrigatória (e a que apanha mais peças)!"
            if resultado is None and side != hum_side:
                if not box["busy"]:
                    pensar()
                    msg = "A IA está a pensar..."
                elif box["res"] is not None:
                    m, k = box["res"]
                    box["res"], box["busy"] = None, False
                    lances.append((k, damas_str_mov(m)))
                    jogar_mov(m)
            # desenho
            comum_fundo(screen)
            comum_texto(screen, "Damas", (comum_W // 2, 32), 28, comum_TXT, "center")
            pygame.draw.rect(screen, (60, 36, 18), (BX - 14, BY - 14, 8 * SQ + 28, 8 * SQ + 28), border_radius=10)
            for s in range(64):
                x, y = xy(s)
                col = (118, 78, 46) if damas_DARK[s] else (232, 212, 170)
                pygame.draw.rect(screen, col, (x, y, SQ, SQ))
            if last:
                for s in last:
                    x, y = xy(s)
                    pygame.draw.rect(screen, (200, 190, 80), (x, y, SQ, SQ), 4)
            if sel is not None:
                x, y = xy(sel)
                pygame.draw.rect(screen, (90, 200, 120), (x, y, SQ, SQ), 5)
                for m in moves:
                    if m[0] == sel:
                        x, y = xy(m[1])
                        pygame.draw.circle(screen, (90, 200, 120), (x + SQ // 2, y + SQ // 2), 11)
            for s in range(64):
                p = b[s]
                if not p:
                    continue
                x, y = xy(s)
                c = (x + SQ // 2, y + SQ // 2)
                white = p > 0
                base = (240, 236, 226) if white else (46, 40, 40)
                rim = (170, 160, 140) if white else (10, 8, 8)
                pygame.draw.circle(screen, (0, 0, 0), (c[0] + 2, c[1] + 4), SQ // 2 - 9)
                pygame.draw.circle(screen, rim, c, SQ // 2 - 9)
                pygame.draw.circle(screen, base, c, SQ // 2 - 13)
                pygame.draw.circle(screen, rim, c, SQ // 2 - 22, 2)
                if abs(p) == 2:
                    pygame.draw.circle(screen, (235, 190, 50), c, SQ // 2 - 26)
                    pygame.draw.circle(screen, (150, 110, 20), c, SQ // 2 - 26, 2)
            if resultado is None and side == hum_side and forced:
                for m in {m[0] for m in moves}:
                    x, y = xy(m)
                    pygame.draw.rect(screen, (220, 90, 70), (x + 2, y + 2, SQ - 4, SQ - 4), 2)
            px = BX + 8 * SQ + 50
            brancas = sum(1 for p in b if p > 0)
            pretas = sum(1 for p in b if p < 0)
            comum_texto(screen, f"Nível: {nivel}", (px, 120), 22)
            comum_texto(screen, f"Brancas: {brancas}", (px, 170), 19, (240, 236, 226))
            comum_texto(screen, f"Pretas: {pretas}", (px, 200), 19, (170, 165, 165))
            comum_texto(screen, "Tu: " + ("brancas" if hum_side == 1 else "pretas"), (px, 245), 18, comum_OURO)
            if info["d"] and resultado is None and side != hum_side:
                comum_texto(screen, f"profundidade {info['d']}", (px, 285), 16, comum_DIM, bold=False)
            comum_texto(screen, f"Experiência guardada: {len(exp.d)} posições", (px, 325), 15, comum_DIM, bold=False)
            comum_texto(screen, "Captura obrigatória, pela maioria.", (px, 365), 15, comum_DIM, bold=False)
            comum_texto(screen, "Dama anda e come à distância.", (px, 388), 15, comum_DIM, bold=False)
            comum_texto(screen, "R = nova partida   ESC = menu", (px, 430), 15, comum_DIM, bold=False)
            comum_texto(screen, msg, (BX, 672), 22, comum_OURO)
            pygame.display.flip()
            clock.tick(60)
        hum_side = -hum_side           # alterna as cores na revanche
        flip = (hum_side == -1)


def damas_veredito(resultado, hum_side):
    if resultado == 0:
        return "draw"
    return "win" if resultado == hum_side else "loss"



# ========================================================================
# XADREZ — código integrado
# ========================================================================


"""Xadrez."""
import glob
import os
import random
import shutil
import subprocess
import threading
import time


# Tabelas
xadrez_P_, xadrez_N_, xadrez_B_, xadrez_R_, xadrez_Q_, xadrez_K_ = 1, 2, 3, 4, 5, 6
xadrez_DIRS8 = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]   # 0-3 torre, 4-7 bispo
xadrez_RAY = [[[] for _ in range(8)] for _ in range(64)]
xadrez_KN = [[] for _ in range(64)]
xadrez_KG = [[] for _ in range(64)]
xadrez_PATT = [[[] for _ in range(64)] for _ in range(2)]      # PATT[cor][sq] = casas de onde um peão dessa cor ataca sq
for _s in range(64):
    _r, _f = divmod(_s, 8)
    for _i, (_dr, _df) in enumerate(xadrez_DIRS8):
        _rr, _ff = _r + _dr, _f + _df
        while 0 <= _rr < 8 and 0 <= _ff < 8:
            xadrez_RAY[_s][_i].append(_rr * 8 + _ff)
            _rr += _dr
            _ff += _df
        if 0 <= _r + _dr < 8 and 0 <= _f + _df < 8:
            xadrez_KG[_s].append((_r + _dr) * 8 + _f + _df)
    for _dr, _df in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
        if 0 <= _r + _dr < 8 and 0 <= _f + _df < 8:
            xadrez_KN[_s].append((_r + _dr) * 8 + _f + _df)
    for _df in (-1, 1):
        if 0 <= _f + _df < 8:
            if _r - 1 >= 0:
                xadrez_PATT[0][_s].append((_r - 1) * 8 + _f + _df)
            if _r + 1 < 8:
                xadrez_PATT[1][_s].append((_r + 1) * 8 + _f + _df)

xadrez_rnd = random.Random(0xC0FFEE)
xadrez_ZP = [[xadrez_rnd.getrandbits(64) for _ in range(64)] for _ in range(16)]
xadrez_ZS = xadrez_rnd.getrandbits(64)
xadrez_ZC = [xadrez_rnd.getrandbits(64) for _ in range(16)]
xadrez_ZE = [0] + [xadrez_rnd.getrandbits(64) for _ in range(64)]
xadrez_CR_MASK = [15] * 64
xadrez_CR_MASK[4], xadrez_CR_MASK[7], xadrez_CR_MASK[0] = 12, 14, 13
xadrez_CR_MASK[60], xadrez_CR_MASK[63], xadrez_CR_MASK[56] = 3, 11, 7

xadrez_VAL = [0, 100, 320, 330, 500, 900, 20000]
xadrez_PH = [0, 0, 1, 1, 2, 4, 0]
xadrez_PST = {
    1: [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0, 5, -5, -10, 0, 0, -10, -5, 5, 5, 10, 10, -20, -20, 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0],
    2: [-50, -40, -30, -30, -30, -30, -40, -50, -40, -20, 0, 0, 0, 0, -20, -40, -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30, -30, 0, 15, 20, 20, 15, 0, -30, -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40, -50, -40, -30, -30, -30, -30, -40, -50],
    3: [-20, -10, -10, -10, -10, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10, -10, 0, 10, 10, 10, 10, 0, -10, -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10, -20, -10, -10, -10, -10, -10, -10, -20],
    4: [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, -5, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, 5, 5, 0, 0, 0],
    5: [-20, -10, -10, -5, -5, -10, -10, -20, -10, 0, 0, 0, 0, 0, 0, -10, -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5, 0, 0, 5, 5, 5, 5, 0, -5, -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10, -20, -10, -10, -5, -5, -10, -10, -20],
    6: [-30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30, -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30, -20, -30, -30, -40, -40, -30, -30, -20, -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20],
}
xadrez_KING_EG = [-50, -40, -30, -20, -20, -30, -40, -50, -30, -20, -10, 0, 0, -10, -20, -30, -30, -10, 20, 30, 30, 20, -10, -30,
            -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 30, 40, 40, 30, -10, -30, -30, -10, 20, 30, 30, 20, -10, -30,
            -30, -30, 0, 0, 0, 0, -30, -30, -50, -30, -30, -30, -30, -30, -30, -50]
xadrez_PAWN_EG = [0] * 8 + [90] * 8 + [50] * 8 + [30] * 8 + [15] * 8 + [5] * 8 + [0] * 16
xadrez_MGT = [[0] * 64 for _ in range(16)]
xadrez_EGT = [[0] * 64 for _ in range(16)]
for _t in range(1, 7):
    for _c in (0, 1):
        _p = _t | (_c << 3)
        for _s in range(64):
            _r, _f = divmod(_s, 8)
            _i = (7 - _r) * 8 + _f if _c == 0 else _r * 8 + _f
            xadrez_MGT[_p][_s] = xadrez_VAL[_t] + xadrez_PST[_t][_i] if _t != 6 else xadrez_PST[6][_i]
            if _t == 1:
                xadrez_EGT[_p][_s] = xadrez_VAL[1] + 20 + xadrez_PAWN_EG[_i]
            elif _t == 6:
                xadrez_EGT[_p][_s] = xadrez_KING_EG[_i]
            else:
                xadrez_EGT[_p][_s] = xadrez_VAL[_t] + xadrez_PST[_t][_i]

xadrez_MATE = 30000
xadrez_INF = 10 ** 9
xadrez_LETRAS = {2: "C", 3: "B", 4: "T", 5: "D", 6: "R"}
xadrez_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def xadrez_sq_nome(s):
    return "abcdefgh"[s & 7] + str(s // 8 + 1)


def xadrez_sq_de(nome):
    return "abcdefgh".index(nome[0]) + 8 * (int(nome[1]) - 1)


def xadrez_m_uci(m):
    pr = (m >> 12) & 7
    return xadrez_sq_nome(m & 63) + xadrez_sq_nome((m >> 6) & 63) + ("" if not pr else "nbrq"[pr - 2])


# Posição
class xadrez_Pos:
    def __init__(self, fen=xadrez_START_FEN):
        self.b = [0] * 64
        self.stack = []
        self.cnt = [0] * 16
        self.ksq = [4, 60]
        self.mg = self.eg = self.ph = 0
        self.h = 0
        parts = fen.split()
        r = 7
        f = 0
        codes = {c: i + 1 for i, c in enumerate("pnbrqk")}
        for ch in parts[0]:
            if ch == "/":
                r -= 1
                f = 0
            elif ch.isdigit():
                f += int(ch)
            else:
                t = codes[ch.lower()]
                p = t | (0 if ch.isupper() else 8)
                self._put(r * 8 + f, p)
                if t == 6:
                    self.ksq[0 if ch.isupper() else 1] = r * 8 + f
                f += 1
        self.side = 0 if parts[1] == "w" else 1
        self.castle = 0
        for ch, bit in (("K", 1), ("Q", 2), ("k", 4), ("q", 8)):
            if ch in parts[2]:
                self.castle |= bit
        self.ep = xadrez_sq_de(parts[3]) if parts[3] != "-" else -1
        self.half = int(parts[4]) if len(parts) > 4 else 0
        self.full = int(parts[5]) if len(parts) > 5 else 1
        self.h ^= (xadrez_ZS if self.side else 0) ^ xadrez_ZC[self.castle] ^ xadrez_ZE[self.ep + 1]
        self.hist = [self.h]

    def _put(self, s, p):
        self.b[s] = p
        self.h ^= xadrez_ZP[p][s]
        sg = 1 if p < 8 else -1
        self.mg += sg * xadrez_MGT[p][s]
        self.eg += sg * xadrez_EGT[p][s]
        self.ph += xadrez_PH[p & 7]
        self.cnt[p] += 1

    def copy(self):
        o = xadrez_Pos.__new__(xadrez_Pos)
        o.b, o.cnt, o.ksq, o.hist = self.b[:], self.cnt[:], self.ksq[:], self.hist[:]
        o.stack = []
        o.mg, o.eg, o.ph, o.h = self.mg, self.eg, self.ph, self.h
        o.side, o.castle, o.ep, o.half, o.full = self.side, self.castle, self.ep, self.half, self.full
        return o

    def attacked(self, sq, by):
        b = self.b
        cb = by << 3
        pw = 1 | cb
        for s in xadrez_PATT[by][sq]:
            if b[s] == pw:
                return True
        nt = 2 | cb
        for s in xadrez_KN[sq]:
            if b[s] == nt:
                return True
        kt = 6 | cb
        for s in xadrez_KG[sq]:
            if b[s] == kt:
                return True
        rk, qn, bs = 4 | cb, 5 | cb, 3 | cb
        for d in range(4):
            for s in xadrez_RAY[sq][d]:
                q = b[s]
                if q:
                    if q == rk or q == qn:
                        return True
                    break
        for d in range(4, 8):
            for s in xadrez_RAY[sq][d]:
                q = b[s]
                if q:
                    if q == bs or q == qn:
                        return True
                    break
        return False

    def in_check(self):
        return self.attacked(self.ksq[self.side], 1 - self.side)

    def gen(self, caps=False):
        b, side, out = self.b, self.side, []
        mb = side << 3
        ep = self.ep
        for fr in range(64):
            p = b[fr]
            if not p or (p & 8) != mb:
                continue
            t = p & 7
            if t == 1:
                r, f = fr >> 3, fr & 7
                fwd, start, pr_r = (8, 1, 6) if side == 0 else (-8, 6, 1)
                for df in (-1, 1):
                    nf = f + df
                    if 0 <= nf < 8:
                        t2 = fr + fwd + df
                        q = b[t2]
                        if q:
                            if (q & 8) != mb:
                                if r == pr_r:
                                    for pr in ((5,) if caps else (5, 4, 3, 2)):
                                        out.append(fr | t2 << 6 | pr << 12)
                                else:
                                    out.append(fr | t2 << 6)
                        elif t2 == ep:
                            out.append(fr | t2 << 6)
                to = fr + fwd
                if not b[to]:
                    if r == pr_r:
                        for pr in ((5,) if caps else (5, 4, 3, 2)):
                            out.append(fr | to << 6 | pr << 12)
                    elif not caps:
                        out.append(fr | to << 6)
                        if r == start and not b[to + fwd]:
                            out.append(fr | (to + fwd) << 6)
            elif t == 2 or t == 6:
                for to in (xadrez_KN[fr] if t == 2 else xadrez_KG[fr]):
                    q = b[to]
                    if q:
                        if (q & 8) != mb:
                            out.append(fr | to << 6)
                    elif not caps:
                        out.append(fr | to << 6)
                if t == 6 and not caps:
                    if side == 0 and fr == 4:
                        if self.castle & 1 and not b[5] and not b[6] and b[7] == 4 \
                                and not self.attacked(4, 1) and not self.attacked(5, 1):
                            out.append(4 | 6 << 6)
                        if self.castle & 2 and not b[3] and not b[2] and not b[1] and b[0] == 4 \
                                and not self.attacked(4, 1) and not self.attacked(3, 1):
                            out.append(4 | 2 << 6)
                    elif side == 1 and fr == 60:
                        if self.castle & 4 and not b[61] and not b[62] and b[63] == 12 \
                                and not self.attacked(60, 0) and not self.attacked(61, 0):
                            out.append(60 | 62 << 6)
                        if self.castle & 8 and not b[59] and not b[58] and not b[57] and b[56] == 12 \
                                and not self.attacked(60, 0) and not self.attacked(59, 0):
                            out.append(60 | 58 << 6)
            else:
                lo, hi = (4, 8) if t == 3 else ((0, 4) if t == 4 else (0, 8))
                for d in range(lo, hi):
                    for to in xadrez_RAY[fr][d]:
                        q = b[to]
                        if q:
                            if (q & 8) != mb:
                                out.append(fr | to << 6)
                            break
                        if not caps:
                            out.append(fr | to << 6)
        return out

    def make(self, m):
        b = self.b
        fr, to, pr = m & 63, (m >> 6) & 63, (m >> 12) & 7
        p, cap, side = b[fr], b[to], self.side
        self.stack.append((m, cap, self.castle, self.ep, self.half, self.h, self.mg, self.eg, self.ph,
                           self.ksq[0], self.ksq[1]))
        h = self.h ^ xadrez_ZS ^ xadrez_ZC[self.castle] ^ xadrez_ZE[self.ep + 1]
        mg, eg, ph = self.mg, self.eg, self.ph
        sg = 1 if side == 0 else -1
        t = p & 7
        h ^= xadrez_ZP[p][fr]
        mg -= sg * xadrez_MGT[p][fr]
        eg -= sg * xadrez_EGT[p][fr]
        b[fr] = 0
        if cap:
            h ^= xadrez_ZP[cap][to]
            mg += sg * xadrez_MGT[cap][to]
            eg += sg * xadrez_EGT[cap][to]
            ph -= xadrez_PH[cap & 7]
            self.cnt[cap] -= 1
        newep = -1
        if t == 1:
            if to == self.ep and not cap and (fr & 7) != (to & 7):
                cs = to - 8 if side == 0 else to + 8
                cp = b[cs]
                h ^= xadrez_ZP[cp][cs]
                mg += sg * xadrez_MGT[cp][cs]
                eg += sg * xadrez_EGT[cp][cs]
                b[cs] = 0
                self.cnt[cp] -= 1
            elif abs(to - fr) == 16:
                newep = (fr + to) >> 1
        placed = p
        if pr:
            placed = pr | (p & 8)
            ph += xadrez_PH[pr]
            self.cnt[p] -= 1
            self.cnt[placed] += 1
        b[to] = placed
        h ^= xadrez_ZP[placed][to]
        mg += sg * xadrez_MGT[placed][to]
        eg += sg * xadrez_EGT[placed][to]
        if t == 6:
            self.ksq[side] = to
            if to - fr == 2 or fr - to == 2:
                rf, rt = (fr + 3, fr + 1) if to > fr else (fr - 4, fr - 1)
                rk = b[rf]
                b[rf] = 0
                b[rt] = rk
                h ^= xadrez_ZP[rk][rf] ^ xadrez_ZP[rk][rt]
                mg += sg * (xadrez_MGT[rk][rt] - xadrez_MGT[rk][rf])
                eg += sg * (xadrez_EGT[rk][rt] - xadrez_EGT[rk][rf])
        self.castle &= xadrez_CR_MASK[fr] & xadrez_CR_MASK[to]
        self.ep = newep
        self.half = 0 if (t == 1 or cap) else self.half + 1
        if side:
            self.full += 1
        self.side = 1 - side
        self.mg, self.eg, self.ph = mg, eg, ph
        self.h = h ^ xadrez_ZC[self.castle] ^ xadrez_ZE[newep + 1]
        self.hist.append(self.h)

    def unmake(self):
        m, cap, castle, ep, half, h, mg, eg, ph, wk, bk = self.stack.pop()
        self.hist.pop()
        b = self.b
        fr, to, pr = m & 63, (m >> 6) & 63, (m >> 12) & 7
        side = 1 - self.side
        placed = b[to]
        p = (1 | (side << 3)) if pr else placed
        b[fr] = p
        b[to] = cap
        if pr:
            self.cnt[placed] -= 1
            self.cnt[p] += 1
        t = p & 7
        if cap:
            self.cnt[cap] += 1
        if t == 1 and to == ep and not cap and (fr & 7) != (to & 7):
            cs = to - 8 if side == 0 else to + 8
            ps = 1 | ((1 - side) << 3)
            b[cs] = ps
            self.cnt[ps] += 1
        if t == 6 and (to - fr == 2 or fr - to == 2):
            rf, rt = (fr + 3, fr + 1) if to > fr else (fr - 4, fr - 1)
            b[rf] = b[rt]
            b[rt] = 0
        self.castle, self.ep, self.half, self.h = castle, ep, half, h
        self.mg, self.eg, self.ph = mg, eg, ph
        self.ksq[0], self.ksq[1] = wk, bk
        if side:
            self.full -= 1
        self.side = side

    def make_null(self):
        self.stack.append((0, 0, self.castle, self.ep, self.half, self.h, self.mg, self.eg, self.ph, 0, 0))
        self.h ^= xadrez_ZS ^ xadrez_ZE[self.ep + 1]
        self.ep = -1
        self.side = 1 - self.side
        self.half += 1
        self.hist.append(self.h)

    def unmake_null(self):
        m, cap, castle, ep, half, h, mg, eg, ph, a, c = self.stack.pop()
        self.hist.pop()
        self.castle, self.ep, self.half, self.h = castle, ep, half, h
        self.side = 1 - self.side

    def legal(self):
        out = []
        side = self.side
        for m in self.gen():
            self.make(m)
            if not self.attacked(self.ksq[side], 1 - side):
                out.append(m)
            self.unmake()
        return out

    def repetido(self):
        hs = self.hist
        n = len(hs)
        h = self.h
        for j in range(n - 3, max(-1, n - 2 - self.half), -2):
            if hs[j] == h:
                return True
        return False

    def eval(self):
        ph = self.ph if self.ph < 24 else 24
        mg, eg = self.mg, self.eg
        s = (mg * ph + eg * (24 - ph)) // 24
        c = self.cnt
        if c[3] >= 2:
            s += 30
        if c[11] >= 2:
            s -= 30
        if ph <= 10:                                   # final: empurrar o rei adversário para a borda
            mw = c[2] * 320 + c[3] * 330 + c[4] * 500 + c[5] * 900
            mb = c[10] * 320 + c[11] * 330 + c[12] * 500 + c[13] * 900
            if mw - mb >= 300 and not c[9]:
                s += self._mop(self.ksq[1], self.ksq[0])
            elif mb - mw >= 300 and not c[1]:
                s -= self._mop(self.ksq[0], self.ksq[1])
        return (s if self.side == 0 else -s) + 8

    @staticmethod
    def _mop(loser, winner):
        lr, lf = divmod(loser, 8)
        wr, wf = divmod(winner, 8)
        cd = max(3 - lr, lr - 4) + max(3 - lf, lf - 4)
        return 10 * cd + 4 * (14 - abs(lr - wr) - abs(lf - wf))

    def tem_pecas(self):
        c = self.cnt
        o = 0 if self.side == 0 else 8
        return c[2 | o] + c[3 | o] + c[4 | o] + c[5 | o] > 0

    def material_insuficiente(self):
        c = self.cnt
        if c[1] or c[9] or c[4] or c[12] or c[5] or c[13]:
            return False
        menores = c[2] + c[3] + c[10] + c[11]
        if menores <= 1:
            return True
        if menores == 2 and c[3] == 1 and c[11] == 1:
            ws = [s for s in range(64) if self.b[s] == 3][0]
            bs = [s for s in range(64) if self.b[s] == 11][0]
            return (ws // 8 + ws % 8) % 2 == (bs // 8 + bs % 8) % 2
        return False

    def san(self, m):
        b = self.b
        fr, to, pr = m & 63, (m >> 6) & 63, (m >> 12) & 7
        p = b[fr]
        t = p & 7
        if t == 6 and abs(to - fr) == 2:
            s = "O-O" if to > fr else "O-O-O"
        else:
            cap = b[to] != 0 or (t == 1 and (fr & 7) != (to & 7))
            s = ""
            if t == 1:
                if cap:
                    s += "abcdefgh"[fr & 7]
            else:
                s += xadrez_LETRAS[t]
                outros = [x for x in self.legal() if x != m and (x >> 6) & 63 == to and b[x & 63] == p]
                if outros:
                    if all((x & 7) != (fr & 7) for x in outros):
                        s += "abcdefgh"[fr & 7]
                    elif all((x & 63) >> 3 != fr >> 3 for x in outros):
                        s += str(fr // 8 + 1)
                    else:
                        s += xadrez_sq_nome(fr)
            if cap:
                s += "x"
            s += xadrez_sq_nome(to)
            if pr:
                s += "=" + {2: "C", 3: "B", 4: "T", 5: "D"}[pr]
        self.make(m)
        if self.in_check():
            s += "#" if not self.legal() else "+"
        self.unmake()
        return s


# Motor de busca
class xadrez_Timeout(Exception):
    pass


class xadrez_Motor:
    def __init__(self):
        self.tt = {}
        self.killers = [[0, 0] for _ in range(128)]
        self.hist = {}
        self.nodes = 0
        self.deadline = None

    def _tick(self):
        self.nodes += 1
        if self.deadline is not None and (self.nodes & 1023) == 0 and time.time() > self.deadline:
            raise xadrez_Timeout

    def _order(self, pos, moves, tmove, ply):
        b = pos.b
        k1, k2 = self.killers[ply]
        hist = self.hist
        ep = pos.ep
        sc = []
        for m in moves:
            to = (m >> 6) & 63
            cap = b[to]
            if m == tmove:
                s = 10 ** 8
            elif cap:
                s = 10 ** 6 + xadrez_VAL[cap & 7] * 10 - xadrez_VAL[b[m & 63] & 7] // 10
            elif m >> 12:
                s = 9 * 10 ** 5 + (m >> 12)
            elif (b[m & 63] & 7) == 1 and to == ep:
                s = 10 ** 6 + 900
            elif m == k1:
                s = 8 * 10 ** 5
            elif m == k2:
                s = 7 * 10 ** 5
            else:
                s = hist.get(m & 4095, 0)
            sc.append((s, m))
        sc.sort(reverse=True)
        return [m for _, m in sc]

    def qs(self, pos, alpha, beta, ply):
        self._tick()
        stand = pos.eval()
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if ply >= 90:
            return stand
        side = pos.side
        b = pos.b
        for m in self._order(pos, pos.gen(True), 0, ply):
            to = (m >> 6) & 63
            if not (m >> 12) and stand + xadrez_VAL[b[to] & 7] + 220 < alpha and b[to]:
                continue
            pos.make(m)
            if pos.attacked(pos.ksq[side], 1 - side):
                pos.unmake()
                continue
            v = -self.qs(pos, -beta, -alpha, ply + 1)
            pos.unmake()
            if v >= beta:
                return v
            if v > alpha:
                alpha = v
        return alpha

    def ab(self, pos, depth, alpha, beta, ply, nullok=True):
        self._tick()
        if pos.half >= 100 or pos.repetido():
            return 0
        side = pos.side
        incheck = pos.attacked(pos.ksq[side], 1 - side)
        if incheck:
            depth += 1
        if depth <= 0:
            return self.qs(pos, alpha, beta, ply)
        key = pos.h
        ent = self.tt.get(key)
        tmove = 0
        if ent is not None:
            d, fl, v, tmove = ent
            if d >= depth:
                if v > xadrez_MATE - 200:
                    v -= ply
                elif v < -xadrez_MATE + 200:
                    v += ply
                if fl == 0:
                    return v
                if fl == 1 and v > alpha:
                    alpha = v
                elif fl == 2 and v < beta:
                    beta = v
                if alpha >= beta:
                    return v
        if nullok and not incheck and depth >= 3 and beta < xadrez_MATE - 200 and pos.tem_pecas() \
                and pos.eval() >= beta:
            pos.make_null()
            v = -self.ab(pos, depth - 3 - (depth >= 6), -beta, -beta + 1, ply + 1, False)
            pos.unmake_null()
            if v >= beta:
                return beta
        moves = self._order(pos, pos.gen(), tmove, ply)
        a0 = alpha
        legal = 0
        best, bm = -xadrez_INF, 0
        b = pos.b
        for m in moves:
            to = (m >> 6) & 63
            quiet = not b[to] and not (m >> 12)
            pos.make(m)
            if pos.attacked(pos.ksq[side], 1 - side):
                pos.unmake()
                continue
            legal += 1
            nd = depth - 1
            if legal == 1:
                v = -self.ab(pos, nd, -beta, -alpha, ply + 1)
            else:
                red = 0
                if depth >= 3 and legal > 4 and quiet and not incheck:
                    red = 1 + (legal > 10) + (depth > 6 and legal > 6)
                v = -self.ab(pos, nd - red, -alpha - 1, -alpha, ply + 1)
                if v > alpha and red:
                    v = -self.ab(pos, nd, -alpha - 1, -alpha, ply + 1)
                if alpha < v < beta:
                    v = -self.ab(pos, nd, -beta, -alpha, ply + 1)
            pos.unmake()
            if v > best:
                best, bm = v, m
                if v > alpha:
                    alpha = v
                    if alpha >= beta:
                        if quiet:
                            k = self.killers[ply]
                            if k[0] != m:
                                k[1], k[0] = k[0], m
                            self.hist[m & 4095] = self.hist.get(m & 4095, 0) + depth * depth
                        break
        if not legal:
            return -xadrez_MATE + ply if incheck else 0
        if len(self.tt) > 1_200_000:
            self.tt.clear()
        sv = best
        if sv > xadrez_MATE - 200:
            sv += ply
        elif sv < -xadrez_MATE + 200:
            sv -= ply
        self.tt[key] = (depth, 0 if a0 < best < beta else (1 if best >= beta else 2), sv, bm)
        return best

    def buscar(self, pos, tempo=2.0, prof=64, exp=None, info=None):
        root = pos.copy()
        moves = root.legal()
        if not moves:
            return 0, 0, 0
        if len(moves) == 1:
            return moves[0], 0, 0
        self.nodes = 0
        self.hist = {k: v // 4 for k, v in self.hist.items()}
        self.killers = [[0, 0] for _ in range(128)]
        self.deadline = (time.time() + tempo) if tempo else None
        order = self._order(root, moves, 0, 0)
        best, best_v, done = order[0], 0, 0
        try:
            for d in range(1, prof + 1):
                alpha, bm = -xadrez_INF, None
                for i, m in enumerate(order):
                    root.make(m)
                    if i == 0:
                        v = -self.ab(root, d - 1, -xadrez_INF, -alpha, 1)
                    else:
                        v = -self.ab(root, d - 1, -alpha - 1, -alpha, 1)
                        if v > alpha:
                            v = -self.ab(root, d - 1, -xadrez_INF, -alpha, 1)
                    root.unmake()
                    if v > alpha:
                        alpha, bm = v, m
                        best, best_v = m, v
                order = [bm] + [m for m in order if m != bm]
                done = d
                if info:
                    info(d, best_v, xadrez_m_uci(best))
                if abs(best_v) > xadrez_MATE - 100:
                    break
        except xadrez_Timeout:
            pass
        self.deadline = None
        usar_rede = comum_athena_ativo("xadrez")
        if ((exp is not None and exp.tem(comum_chave(pos.h.to_bytes(8, "big")))) or usar_rede) \
                and abs(best_v) < xadrez_MATE - 200:
            best = self._com_experiencia(pos, moves, exp, max(1, done - 1), tempo, best, usar_rede)
        comum_athena_escolha("xadrez", self._descrever(pos, best), (pos.mg, pos.eg, pos.ph, pos.side))
        return best, best_v, done

    @staticmethod
    def _descrever(pos, m):
        fr, to = m & 63, (m >> 6) & 63
        return (fr, to, (m >> 12) & 7, pos.b[fr] & 7, pos.b[to] & 7)

    def _com_experiencia(self, pos, moves, exp, depth, tempo, best, rede=False):
        key = comum_chave(pos.h.to_bytes(8, "big"))
        root = pos.copy()
        self.deadline = time.time() + max(0.6, tempo * 0.4)
        sc = {}
        try:
            for m in moves:
                root.make(m)
                sc[m] = -self.ab(root, depth - 1, -xadrez_INF, xadrez_INF, 1)
                if exp is not None:
                    sc[m] += 70 * max(-1.0, min(0.5, exp.valor(key, xadrez_m_uci(m))))
                root.unmake()
            if rede:
                ordem = list(sc)
                vies = comum_athena_vies("xadrez", [self._descrever(pos, m) for m in ordem], (pos.mg, pos.eg, pos.ph, pos.side))
                if vies:
                    for m, v in zip(ordem, vies):
                        sc[m] += 25.0 * v
            return max(sc, key=sc.get)
        except xadrez_Timeout:
            return best
        finally:
            self.deadline = None


# Stockfish (opcional)
def xadrez_achar_stockfish():
    c = os.environ.get("STOCKFISH")
    if c and os.path.exists(c):
        return c
    w = shutil.which("stockfish")
    if w:
        return w
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in ("stockfish*", "stockfish*/stockfish*", "Stockfish*"):
        for p in glob.glob(os.path.join(here, pat)):
            if os.path.isfile(p) and os.access(p, os.X_OK) and not p.endswith((".txt", ".md", ".py", ".zip")):
                return p
    return None


class xadrez_UCI:
    def __init__(self, path):
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, bufsize=1)
        self._send("uci")
        self._espera("uciok")
        self._send(f"setoption name Threads value {max(1, (os.cpu_count() or 2) - 1)}")
        self._send("setoption name Hash value 256")
        self._send("isready")
        self._espera("readyok")

    def _send(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()

    def _espera(self, palavra):
        while True:
            ln = self.p.stdout.readline()
            if not ln:
                raise RuntimeError("motor UCI terminou")
            if ln.startswith(palavra):
                return ln

    def melhor(self, ucis, ms):
        self._send("position startpos" + (" moves " + " ".join(ucis) if ucis else ""))
        self._send(f"go movetime {int(ms)}")
        return self._espera("bestmove").split()[1]

    def fechar(self):
        try:
            self._send("quit")
            self.p.wait(timeout=2)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


# Livro de aberturas
xadrez_LINHAS = [
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6 e1g1 f8e7 f1e1 b7b5 a4b3 d7d6 c2c3 e8g8",
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6 d2d3 d7d6 e1g1 e8g8",
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5",
    "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6 c1g5 f8e7 e4e5 f6d7 g5e7 d8e7",
    "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6",
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7 e2e3 e8g8 g1f3 b8d7",
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4 e2e3 e8g8 f1d3 d7d5 g1f3 c7c5",
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 g1f3 e8g8 f1e2 e7e5",
    "c2c4 e7e5 b1c3 g8f6 g1f3 b8c6 g2g3 d7d5 c4d5 f6d5 f1g2 d5b6",
    "g1f3 d7d5 g2g3 g8f6 f1g2 e7e6 e1g1 f8e7 d2d4 e8g8",
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 g8f6 d4c6 b7c6 e4e5 d8e7",
    "d2d4 d7d5 g1f3 g8f6 c2c4 e7e6 b1c3 c7c6 e2e3 b8d7 f1d3 d5c4 d3c4 b7b5",
]
xadrez_LIVRO = [l.split() for l in xadrez_LINHAS]


def xadrez_do_livro(ucis):
    n = len(ucis)
    c = [l[n] for l in xadrez_LIVRO if len(l) > n and l[:n] == ucis]
    return random.choice(c) if c else None


xadrez_NIVEIS = {   # tempo (s), profundidade máxima, prob. de lance aleatório, usa livro
    "facil": (0.4, 2, 0.20, True), "normal": (0.8, 3, 0.0, True), "dificil": (2.0, 64, 0.0, True),
    "mestre": (5.0, 64, 0.0, True), "absurdo": (12.0, 64, 0.0, True),
}


class xadrez_Partida:
    def __init__(self):
        self.pos = xadrez_Pos()
        self.ucis = []
        self.sans = []
        self.lances_ia = []
        self.vistos = {self.pos.h: 1}
        self.resultado = None       # (vencedor 0/1/None, texto)
        self.ultimo = None
        self.capturadas = [[], []]
        self.hum = 0                # cor do jogador humano (0 = brancas, 1 = pretas)

    def xadrez_jogar(self, m):
        pos = self.pos
        t = pos.b[(m >> 6) & 63]
        if t == 0 and (pos.b[m & 63] & 7) == 1 and (m & 7) != ((m >> 6) & 7):
            t = 1 | ((1 - pos.side) << 3)
        if t:
            self.capturadas[pos.side].append(t)
        san = pos.san(m)
        self.sans.append(san)
        comum_athena_record_move("xadrez", "jogador" if pos.side == self.hum else "ATHENA", san)
        self.ucis.append(xadrez_m_uci(m))
        pos.make(m)
        self.ultimo = (m & 63, (m >> 6) & 63)
        self.vistos[pos.h] = self.vistos.get(pos.h, 0) + 1
        self.avaliar_fim()

    def avaliar_fim(self):
        pos = self.pos
        if not pos.legal():
            if pos.in_check():
                self.resultado = (1 - pos.side, "Xeque-mate!")
            else:
                self.resultado = (None, "Afogamento (empate)")
        elif self.vistos.get(pos.h, 0) >= 3:
            self.resultado = (None, "Empate por repetição")
        elif pos.half >= 100:
            self.resultado = (None, "Empate (regra dos 50 lances)")
        elif pos.material_insuficiente():
            self.resultado = (None, "Empate (material insuficiente)")


def xadrez_escolher_lance(partida, nivel, motor, uci, exp, info, aleatorio_ok=True):
    tempo, prof, alea, usa_livro = xadrez_NIVEIS[nivel]
    pos = partida.pos
    legais = pos.legal()
    key = comum_chave(pos.h.to_bytes(8, "big"))
    if usa_livro and len(partida.ucis) < 16:
        lv = xadrez_do_livro(partida.ucis)
        if lv:
            for m in legais:
                if xadrez_m_uci(m) == lv and exp.valor(key, lv) > -0.5:
                    return m, key
    if alea and random.random() < alea:
        return random.choice(legais), key
    if nivel == "absurdo" and uci is not None:
        try:
            s = uci.melhor(partida.ucis, tempo * 1000)
            for m in legais:
                if xadrez_m_uci(m) == s:
                    return m, key
        except Exception:
            pass
    m, v, d = motor.buscar(pos, tempo, prof, exp, info)
    return m, key


# Peças desenhadas à mão (não depende de fontes com símbolos de xadrez)
xadrez_PECAS = {}


def xadrez_surf_peca(t, branca, tam):
    import pygame
    k = (t, branca, tam)
    if k in xadrez_PECAS:
        return xadrez_PECAS[k]
    SS = 3
    S = tam * SS
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    fill = (248, 246, 240) if branca else (58, 58, 68)
    line = (30, 30, 36) if branca else (8, 8, 12)
    hi = (190, 190, 200) if branca else (170, 170, 190)
    k_ = S / 100.0

    def xadrez_P_(pts):
        return [(x * k_, y * k_) for x, y in pts]

    def poly(pts, col=fill):
        pygame.draw.polygon(s, col, xadrez_P_(pts))
        pygame.draw.polygon(s, line, xadrez_P_(pts), max(2, SS))

    def circ(x, y, r, col=fill):
        pygame.draw.circle(s, col, (int(x * k_), int(y * k_)), int(r * k_))
        pygame.draw.circle(s, line, (int(x * k_), int(y * k_)), int(r * k_), max(2, SS))

    def rect(x0, y0, x1, y1, col=fill):
        poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], col)

    def base():
        poly([(26, 90), (74, 90), (72, 80), (28, 80)])
        poly([(31, 80), (69, 80), (66, 72), (34, 72)])

    if t == 1:
        poly([(36, 74), (64, 74), (57, 50), (43, 50)])
        rect(37, 46, 63, 53)
        circ(50, 34, 12)
        base()
    elif t == 4:
        poly([(33, 74), (67, 74), (63, 42), (37, 42)])
        poly([(30, 44), (70, 44), (70, 34), (30, 34)])
        rect(28, 20, 38, 34)
        rect(45, 20, 55, 34)
        rect(62, 20, 72, 34)
        rect(28, 30, 72, 36)
        base()
    elif t == 2:
        poly([(30, 74), (72, 74), (70, 56), (66, 40), (58, 26), (48, 18), (42, 24), (24, 46), (26, 54), (38, 50),
              (44, 44), (48, 48), (34, 62)])
        circ(52, 32, 3, line)
        poly([(48, 18), (46, 10), (54, 18)])
        base()
    elif t == 3:
        poly([(36, 74), (64, 74), (58, 52), (42, 52)])
        poly([(50, 14), (64, 34), (60, 50), (40, 50), (36, 34)])
        circ(50, 14, 5)
        pygame.draw.line(s, line, (46 * k_, 36 * k_), (58 * k_, 26 * k_), max(3, SS * 2))
        rect(35, 50, 65, 56)
        base()
    elif t == 5:
        poly([(34, 74), (66, 74), (72, 40), (28, 40)])
        poly([(28, 42), (22, 18), (38, 32), (44, 14), (50, 30), (56, 14), (62, 32), (78, 18), (72, 42)])
        for (x, y) in ((22, 16), (44, 12), (56, 12), (78, 16), (50, 26)):
            circ(x, y, 4.5)
        rect(32, 50, 68, 56)
        base()
    else:
        poly([(34, 74), (66, 74), (70, 40), (30, 40)])
        poly([(30, 42), (36, 26), (64, 26), (70, 42)])
        rect(46, 4, 54, 26)
        rect(39, 10, 61, 18)
        rect(32, 50, 68, 56)
        base()
    pygame.draw.line(s, hi, (40 * k_, 62 * k_), (42 * k_, 50 * k_), max(2, SS)) if t in (1,) else None
    out = pygame.transform.smoothscale(s, (tam, tam))
    xadrez_PECAS[k] = out
    return out


# Interface
def xadrez_jogar(screen, clock, nivel="absurdo", quem_comeca=None):
    import pygame
    exp = comum_Experiencia("xadrez")
    motor = xadrez_Motor()
    sf = xadrez_achar_stockfish() if nivel == "absurdo" else None
    uci = None
    if sf:
        try:
            uci = xadrez_UCI(sf)
        except Exception:
            uci = None
    c0 = quem_comeca if quem_comeca is not None else comum_escolher(
        screen, clock, "Xadrez", ["Jogo com as brancas", "Jogo com as pretas"],
        ["Tu começas", "A IA abre o jogo - bem mais difícil"],
        f"Nível: {nivel}" + ("  |  motor: Stockfish" if uci else "  |  motor próprio"))
    if c0 in (None, "quit"):
        if uci:
            uci.fechar()
        return c0
    hum = 0 if c0 == 0 else 1
    SQ, BX, BY = 78, 60, 48
    try:
        return xadrez_loop(screen, clock, nivel, exp, motor, uci, hum, SQ, BX, BY)
    finally:
        if uci:
            uci.fechar()


def xadrez_loop(screen, clock, nivel, exp, motor, uci, hum, SQ, BX, BY):
    import pygame
    flip = (hum == 1)

    def xy(s):
        r, f = divmod(s, 8)
        return (BX + (7 - f) * SQ, BY + r * SQ) if flip else (BX + f * SQ, BY + (7 - r) * SQ)

    def casa_em(pos):
        c, rr = (pos[0] - BX) // SQ, (pos[1] - BY) // SQ
        if not (0 <= c < 8 and 0 <= rr < 8):
            return None
        return (rr * 8 + (7 - c)) if flip else ((7 - rr) * 8 + c)

    while True:
        motor = xadrez_Motor()                             # motor novo: uma pesquisa antiga nunca interfere com a nova
        G = xadrez_Partida()
        G.hum = hum
        comum_athena_nova_partida("xadrez")
        sel = None
        promo = None            # (fr, to) à espera de escolha
        legais = G.pos.legal()
        box = {"res": None, "busy": False}
        info = {"d": 0, "v": 0, "m": ""}
        msg = ""
        gravado = False
        running = True

        def acabar():
            nonlocal gravado, msg
            if gravado or G.resultado is None:
                return
            gravado = True
            v, txt = G.resultado
            if v is None:
                comum_registar_resultado("xadrez", nivel, "e")
                exp.registar(G.lances_ia, 0)
                msg = txt
            elif v == hum:
                comum_registar_resultado("xadrez", nivel, "v")
                exp.registar(G.lances_ia, -1)
                msg = "Ganhaste! " + txt
            else:
                comum_registar_resultado("xadrez", nivel, "d")
                exp.registar(G.lances_ia, +1)
                msg = "A IA ganhou. " + txt

        def executar(m):
            nonlocal legais, sel, promo, msg
            G.jogar(m)
            legais = G.pos.legal()
            sel, promo = None, None
            msg = "Xeque!" if (G.pos.in_check() and G.resultado is None) else ""
            acabar()

        def pensar():
            box["busy"] = True
            snap = xadrez_Partida.__new__(xadrez_Partida)
            snap.__dict__.update(G.__dict__)
            snap.pos = G.pos.copy()
            snap.ucis = list(G.ucis)

            def inf(d, v, m):
                info["d"], info["v"], info["m"] = d, v, m

            def work():
                try:
                    box["res"] = xadrez_escolher_lance(snap, nivel, motor, uci, exp, inf)
                except Exception as ex:                       # a IA nunca deve encravar o jogo
                    print("Erro na IA:", repr(ex))
                    lg = snap.pos.legal()
                    box["res"] = (random.choice(lg), comum_chave(snap.pos.h.to_bytes(8, "big")))
            threading.Thread(target=work, daemon=True).start()

        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return "quit"
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_F11:
                        try:
                            pygame.display.toggle_fullscreen()
                        except pygame.error:
                            pass
                        continue
                    if e.key == pygame.K_ESCAPE:
                        return "menu"
                    if G.resultado is not None and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return xadrez_veredito(G.resultado, hum)
                    if e.key == pygame.K_f:
                        flip = not flip
                    if e.key == pygame.K_r:
                        if G.resultado is None and G.ucis and not gravado:
                            comum_registar_resultado("xadrez", nivel, "d")
                        running = False
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and G.resultado is not None:
                    return xadrez_veredito(G.resultado, hum)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and G.resultado is None \
                        and G.pos.side == hum and not box["busy"]:
                    if promo is not None:
                        fr, to = promo
                        x0 = BX + 8 * SQ // 2 - 2 * SQ
                        for i, pr in enumerate((5, 4, 3, 2)):
                            if pygame.Rect(x0 + i * SQ, BY + 4 * SQ - SQ // 2, SQ, SQ).collidepoint(e.pos):
                                for m in legais:
                                    if m & 63 == fr and (m >> 6) & 63 == to and (m >> 12) & 7 == pr:
                                        executar(m)
                        promo = None
                        continue
                    s = casa_em(e.pos)
                    if s is None:
                        continue
                    alvo = [m for m in legais if m & 63 == sel and (m >> 6) & 63 == s] if sel is not None else []
                    if alvo:
                        if alvo[0] >> 12:
                            promo = (sel, s)
                        else:
                            executar(alvo[0])
                    elif G.pos.b[s] and (G.pos.b[s] >> 3) == hum and any(m & 63 == s for m in legais):
                        sel = s
                    else:
                        sel = None
            if G.resultado is None and G.pos.side != hum:
                if not box["busy"]:
                    pensar()
                    msg = "A IA está a pensar..."
                elif box["res"] is not None:
                    m, k = box["res"]
                    box["res"], box["busy"] = None, False
                    G.lances_ia.append((k, xadrez_m_uci(m)))
                    executar(m)
            comum_fundo(screen)
            comum_texto(screen, "Xadrez", (comum_W // 2, 32), 28, comum_TXT, "center")
            pygame.draw.rect(screen, (52, 34, 20), (BX - 16, BY - 16, 8 * SQ + 32, 8 * SQ + 32), border_radius=10)
            for s in range(64):
                x, y = xy(s)
                claro = ((s >> 3) + (s & 7)) % 2 == 1
                pygame.draw.rect(screen, (236, 216, 178) if claro else (166, 118, 78), (x, y, SQ, SQ))
            for i in range(8):
                cf = "abcdefgh"[7 - i if flip else i]
                rk = str(i + 1 if flip else 8 - i)
                comum_texto(screen, cf, (BX + i * SQ + SQ - 12, BY + 8 * SQ + 2), 12, (200, 190, 170), "topleft")
                comum_texto(screen, rk, (BX - 13, BY + i * SQ + 3), 12, (200, 190, 170), "topleft")
            if G.ultimo:
                for s in G.ultimo:
                    x, y = xy(s)
                    pygame.draw.rect(screen, (214, 200, 90), (x, y, SQ, SQ), 5)
            if G.pos.in_check() and G.resultado is None or (G.resultado and G.resultado[1] == "Xeque-mate!"):
                x, y = xy(G.pos.ksq[G.pos.side])
                pygame.draw.rect(screen, (220, 60, 60), (x, y, SQ, SQ), 5)
            if sel is not None:
                x, y = xy(sel)
                pygame.draw.rect(screen, (90, 200, 120), (x, y, SQ, SQ), 5)
                for m in legais:
                    if m & 63 == sel:
                        x, y = xy((m >> 6) & 63)
                        if G.pos.b[(m >> 6) & 63] or ((G.pos.b[sel] & 7) == 1 and ((m >> 6) & 7) != (sel & 7)):
                            pygame.draw.circle(screen, (90, 200, 120), (x + SQ // 2, y + SQ // 2), SQ // 2 - 4, 5)
                        else:
                            pygame.draw.circle(screen, (90, 200, 120), (x + SQ // 2, y + SQ // 2), 11)
            for s in range(64):
                p = G.pos.b[s]
                if p:
                    x, y = xy(s)
                    screen.blit(xadrez_surf_peca(p & 7, p < 8, SQ - 6), (x + 3, y + 3))
            if promo is not None:
                x0 = BX + 8 * SQ // 2 - 2 * SQ
                pygame.draw.rect(screen, (30, 32, 42), (x0 - 8, BY + 4 * SQ - SQ // 2 - 8, 4 * SQ + 16, SQ + 16), border_radius=10)
                for i, pr in enumerate((5, 4, 3, 2)):
                    pygame.draw.rect(screen, (70, 76, 98), (x0 + i * SQ + 2, BY + 4 * SQ - SQ // 2 + 2, SQ - 4, SQ - 4), border_radius=8)
                    screen.blit(xadrez_surf_peca(pr, hum == 0, SQ - 10), (x0 + i * SQ + 5, BY + 4 * SQ - SQ // 2 + 5))
            # painel lateral
            px = BX + 8 * SQ + 50
            comum_texto(screen, f"Nível: {nivel}", (px, 90), 22)
            comum_texto(screen, ("Motor: Stockfish" if uci else "Motor: próprio (Python)"), (px, 122), 15, comum_DIM, bold=False)
            for i in (0, 1):
                y = 160 + i * 34
                quem = "IA" if i != hum else "Tu"
                comum_texto(screen, f"{quem}:", (px, y + 4), 15, comum_DIM, bold=False)
                xx = px + 40
                for t in G.capturadas[1 - i][-14:]:
                    screen.blit(xadrez_surf_peca(t & 7, t < 8, 24), (xx, y))
                    xx += 15
            comum_texto(screen, "Lances", (px, 240), 18)
            linhas = []
            for i in range(0, len(G.sans), 2):
                linhas.append(f"{i // 2 + 1}. {G.sans[i]}" + (f"   {G.sans[i + 1]}" if i + 1 < len(G.sans) else ""))
            for j, ln in enumerate(linhas[-13:]):
                comum_texto(screen, ln, (px, 270 + j * 22), 16, comum_TXT, bold=False)
            if info["d"] and G.resultado is None and G.pos.side != hum and not uci:
                comum_texto(screen, f"a pensar: profundidade {info['d']}", (px, 570), 15, comum_DIM, bold=False)
            comum_texto(screen, f"Experiência guardada: {len(exp.d)} posições", (px, 600), 15, comum_DIM, bold=False)
            comum_texto(screen, "R = nova partida (alterna cor)   F = virar   ESC = menu", (px, 626), 14, comum_DIM, bold=False)
            comum_texto(screen, msg, (BX, 672), 22, comum_OURO)
            pygame.display.flip()
            clock.tick(60)
        hum = 1 - hum
        flip = (hum == 1)


def xadrez_veredito(resultado, hum):
    if resultado is None or resultado[0] is None:
        return "draw"
    return "win" if resultado[0] == hum else "loss"



# ========================================================================
# BILHAR — código integrado
# ========================================================================


"""Bilhar americano (8 ball)."""
import math
import os
import sys
import argparse
import threading
import numpy as np

# Física / mesa
bilhar_R = 11
bilhar_L, bilhar_T, bilhar_RT, bilhar_B = 100, 100, 1000, 550
bilhar_MID = (bilhar_L + bilhar_RT) / 2
bilhar_CY = (bilhar_T + bilhar_B) / 2
bilhar_POCKETS = np.array([[bilhar_L, bilhar_T], [bilhar_MID, bilhar_T], [bilhar_RT, bilhar_T], [bilhar_L, bilhar_B], [bilhar_MID, bilhar_B], [bilhar_RT, bilhar_B]], float)
bilhar_PR = np.array([26, 22, 26, 26, 22, 26], float)
bilhar_AXES = np.array([[-1, -1], [0, -1], [1, -1], [-1, 1], [0, 1], [1, 1]], float)
for _k in (0, 2, 3, 5):
    bilhar_AXES[_k] /= math.sqrt(2)
bilhar_MAXV = 26.0
bilhar_FR = 0.985
bilhar_VMIN = 0.08
bilhar_E_BALL = 0.95
bilhar_E_RAIL = 0.78
bilhar_SUB = 3
bilhar_HEAD = np.array([300.0, bilhar_CY])
bilhar_RACK = np.array([680.0, bilhar_CY])
bilhar_DX, bilhar_DY = bilhar_R * math.sqrt(3) + 0.6, 2 * bilhar_R + 0.6
bilhar_HERE = os.path.dirname(os.path.abspath(__file__))
bilhar_WEIGHTS = os.path.join(bilhar_HERE, "ia_pesos.npz")


def bilhar_rede_athena():
    return sys.modules.get(__name__)


def bilhar_guardar_npz(path, arrays):
    """Guarda os pesos usando a mesma rotina segura do resto do programa."""
    comum_escrever_npz(path, arrays)


def bilhar_registar_tacada(game, a):
    try:
        sp = a.get("sp")
        if sp is None:
            sp = (0.0, 0.0)
        sx, sy = float(sp[0]), float(sp[1])
        caca = a.get("called")
        extra = f", bola 8 na caçapa {int(caca) + 1}" if caca is not None else ""
        quem = "jogador" if game.turn == 0 else "ATHENA"
        rede = bilhar_rede_athena()
        if rede is not None:
            rede.athena_record_move(
                "bilhar", quem,
                f"tacada {game.shots}: potência {float(a['pw']):.2f}, efeito ({sx:+.2f}, {sy:+.2f}), "
                f"ângulo {math.degrees(float(a['ang'])) % 360:.0f}°{extra}")
    except Exception as exc:
        print("[ATHENA registo/bilhar]", repr(exc))


def bilhar_find_weights():
    if os.path.exists(bilhar_WEIGHTS):
        return bilhar_WEIGHTS
    import glob
    c = sorted(glob.glob(os.path.join(bilhar_HERE, "ia_pesos*.npz")), key=os.path.getmtime)
    return c[-1] if c else bilhar_WEIGHTS


bilhar_PR2 = bilhar_PR * bilhar_PR
bilhar_TRIU = {}


def bilhar_triu(n):
    t = bilhar_TRIU.get(n)
    if t is None:
        t = bilhar_TRIU[n] = np.triu_indices(n, 1)
    return t


def bilhar_group_of(b):
    if b == 0:
        return None
    if b == 8:
        return "eight"
    return "solid" if b < 8 else "stripe"


def bilhar_ids_of(g):
    return list(range(1, 8)) if g == "solid" else list(range(9, 16))


class bilhar_Game:
    def __init__(self, rng=None):
        self.rng = rng or np.random.default_rng()
        self.reset()

    def reset(self):
        self.P = np.zeros((16, 2))
        self.V = np.zeros((16, 2))
        self.on = np.ones(16, bool)
        self.P[0] = bilhar_HEAD
        solids, stripes = list(range(1, 8)), list(range(9, 16))
        self.rng.shuffle(solids)
        self.rng.shuffle(stripes)
        ca, cb = solids.pop(), stripes.pop()
        rest = solids + stripes
        self.rng.shuffle(rest)
        order = [None] * 15
        order[10], order[14], order[4] = ca, cb, 8
        it = iter(rest)
        for k in range(15):
            if order[k] is None:
                order[k] = next(it)
        k = 0
        for i in range(5):
            for j in range(i + 1):
                self.P[order[k]] = bilhar_RACK + [i * bilhar_DX, (j - i / 2) * bilhar_DY]
                k += 1
        self.groups = [None, None]
        self.turn = 0
        self.ball_in_hand = False
        self.over = False
        self.winner = None
        self.shots = 0
        self.first_hit = None
        self.pocketed = []
        self.pocket_of = {}
        self.rail_hit = False
        self.rail_balls = set()
        self.pre_cleared = False
        self.called = None
        self.kitchen = False
        self.spin = np.zeros(2)
        self.cue_dir = np.array([1.0, 0.0])

    def clone(self):
        g = bilhar_Game.__new__(bilhar_Game)
        g.__dict__.update(self.__dict__)
        g.P, g.V, g.on = self.P.copy(), self.V.copy(), self.on.copy()
        g.groups = list(self.groups)
        g.pocketed = list(self.pocketed)
        g.pocket_of = dict(self.pocket_of)
        g.rail_balls = set(self.rail_balls)
        g.spin, g.cue_dir = self.spin.copy(), self.cue_dir.copy()
        return g

    def valid_spot(self, pos):
        x, y = pos
        if not (bilhar_L + bilhar_R <= x <= bilhar_RT - bilhar_R and bilhar_T + bilhar_R <= y <= bilhar_B - bilhar_R):
            return False
        if self.kitchen and x > bilhar_HEAD[0]:
            return False
        if (np.linalg.norm(bilhar_POCKETS - pos, axis=1) < bilhar_PR + bilhar_R).any():
            return False
        for i in range(1, 16):
            if self.on[i] and np.linalg.norm(self.P[i] - pos) < 2 * bilhar_R + 1:
                return False
        return True

    def start_shot(self, angle, power, spin=(0.0, 0.0), called=None):
        self.cue_dir = np.array([math.cos(angle), math.sin(angle)])
        self.V[0] = power * bilhar_MAXV * self.cue_dir
        self.spin = np.array(spin, float)       # [lateral, vertical(+segue/-recua)]
        self.called = called
        self.first_hit = None
        self.pocketed = []
        self.pocket_of = {}
        self.rail_hit = False
        self.rail_balls = set()
        self.shots += 1
        grp = self.groups[self.turn]
        self.pre_cleared = grp in ("solid", "stripe") and not any(self.on[b] for b in bilhar_ids_of(grp))

    def step(self):
        dt = 1.0 / bilhar_SUB
        fr = bilhar_FR ** dt
        P, V = self.P, self.V
        for _ in range(bilhar_SUB):
            idx = np.flatnonzero(self.on)
            if idx.size == 0:
                break
            P[idx] += V[idx] * dt
            V[idx] *= fr
            p = P[idx]
            diff = p[None] - p[:, None]
            d2 = (diff * diff).sum(-1)
            iu = bilhar_triu(len(idx))
            hit = d2[iu] < (2 * bilhar_R) ** 2
            if hit.any():
                for a, b in zip(iu[0][hit], iu[1][hit]):
                    i, j = idx[a], idx[b]
                    dv = P[j] - P[i]
                    d = math.hypot(dv[0], dv[1])
                    if d < 1e-6:
                        dv, d = np.array([1.0, 0.0]), 1.0
                    n = dv / d
                    ov = 2 * bilhar_R - d
                    P[i] -= n * ov / 2
                    P[j] += n * ov / 2
                    vn = float(np.dot(V[i] - V[j], n))
                    if vn > 0:
                        imp = (1 + bilhar_E_BALL) / 2 * vn
                        V[i] -= imp * n
                        V[j] += imp * n
                        if i == 0:
                            if self.first_hit is None:
                                self.first_hit = int(j)
                            if self.spin[1] != 0:          # segue / recua
                                V[0] += self.cue_dir * self.spin[1] * 0.75 * vn
                                self.spin[1] = 0.0
            p = P[idx]
            dq = p[:, None, :] - bilhar_POCKETS[None]
            inside = (dq * dq).sum(-1) < bilhar_PR2[None]
            if inside.any():
                for r in np.flatnonzero(inside.any(1)):
                    b = int(idx[r])
                    self.on[b] = False
                    V[b] = 0
                    self.pocketed.append(b)
                    self.pocket_of[b] = int(np.argmax(inside[r]))
                idx = np.flatnonzero(self.on)
            for ax, lo, hi in ((0, bilhar_L + bilhar_R, bilhar_RT - bilhar_R), (1, bilhar_T + bilhar_R, bilhar_B - bilhar_R)):
                x = P[idx, ax]
                for sgn, m in ((1, idx[x < lo]), (-1, idx[x > hi])):
                    if m.size == 0:
                        continue
                    vb = np.abs(V[m, ax])
                    P[m, ax] = lo if sgn == 1 else hi
                    V[m, ax] = sgn * vb * bilhar_E_RAIL
                    if self.first_hit is not None:
                        self.rail_hit = True
                        self.rail_balls.update(int(q) for q in m)
                    if self.spin[0] != 0 and (m == 0).any():   # efeito lateral na tabela
                        nrm = np.zeros(2)
                        nrm[ax] = sgn
                        tg = np.array([-nrm[1], nrm[0]])
                        V[0] += tg * self.spin[0] * 0.3 * float(vb[int(np.flatnonzero(m == 0)[0])])
                        self.spin[0] *= 0.6
        s2 = (V * V).sum(1)
        V[s2 < bilhar_VMIN * bilhar_VMIN] = 0
        return bool((s2[self.on] >= bilhar_VMIN * bilhar_VMIN).any())

    def _respot(self, b):
        pos = bilhar_RACK + np.array([2 * bilhar_DX, 0.0])
        for _ in range(12):
            if self.valid_spot(pos):
                break
            pos = pos + np.array([2 * bilhar_R + 1.0, 0.0])
        self.P[b], self.V[b], self.on[b] = pos, 0, True

    def end_shot(self):
        cur, opp = self.turn, 1 - self.turn
        brk = self.shots == 1
        pk = [b for b in self.pocketed if b != 0]
        scratch = 0 in self.pocketed
        grp = self.groups[cur]
        fh = self.first_hit
        foul, why = False, ""
        if scratch:
            foul, why = True, "bola branca na caçapa"
        elif fh is None:
            foul, why = True, "não tocou em nenhuma bola"
        else:
            if grp is None:
                bad = fh == 8
            else:
                bad = not (bilhar_group_of(fh) == grp or (fh == 8 and self.pre_cleared))
            if bad:
                foul, why = True, "bola errada primeiro"
            elif brk:
                # Abertura sem penalização por não atingir quatro tabelas.
                pass
            elif not pk and not self.rail_hit:
                foul, why = True, "nenhuma bola tocou na tabela"
        self.kitchen = bool(foul and brk)
        res = {"good": 0, "foul": foul, "scratch": scratch, "msg": ""}
        if 8 in pk:
            if brk:
                pk.remove(8)
                self._respot(8)
            else:
                ok = (grp in ("solid", "stripe") and self.pre_cleared and not foul
                      and self.pocket_of.get(8) == self.called)
                self.winner = cur if ok else opp
                self.over = True
                if ok:
                    res["msg"] = "Bola 8 na caçapa chamada!"
                elif foul:
                    res["msg"] = "Bola 8 com falta - perdeu!"
                elif not self.pre_cleared:
                    res["msg"] = "Bola 8 cedo demais - perdeu!"
                else:
                    res["msg"] = "Bola 8 na caçapa errada - perdeu!"
                self.called = None
                return res
        if grp is None and not foul and pk and not brk:
            g = bilhar_group_of(pk[0])
            self.groups[cur] = g
            self.groups[opp] = "stripe" if g == "solid" else "solid"
            grp = g
        if grp:
            good = [b for b in pk if bilhar_group_of(b) == grp]
        else:
            good = [] if foul else list(pk)
        res["good"] = len(good)
        if scratch:
            self.on[0] = True
            self.P[0], self.V[0] = bilhar_HEAD, 0
        if foul:
            self.turn = opp
            self.ball_in_hand = True
            res["msg"] = f"Falta ({why}) - bola na mão" + (" atrás da linha" if self.kitchen else "")
        elif good:
            res["msg"] = "Boa! Joga outra vez"
        else:
            self.turn = opp
            res["msg"] = "Passa a vez"
        self.called = None
        return res

    def targets(self, player):
        g = self.groups[player]
        if g is None:
            return [b for b in range(1, 16) if b != 8 and self.on[b]]
        own = [b for b in bilhar_ids_of(g) if self.on[b]]
        return own if own else [8]


# IA: rede de pontuação de tacadas + treino por reforço + pesquisa por simulação
bilhar_POWERS = (0.30, 0.55, 0.85)
bilhar_NF = 17


def bilhar_blocked(game, a, b, exclude):
    ids = [i for i in range(16) if game.on[i] and i not in exclude]
    if not ids:
        return False
    p = game.P[ids]
    ab = b - a
    l2 = float(ab @ ab)
    if l2 < 1e-9:
        return False
    t = np.clip(((p - a) @ ab) / l2, 0, 1)
    d = np.linalg.norm(p - (a + t[:, None] * ab), axis=1)
    return bool((d < 2 * bilhar_R * 0.98).any())


def bilhar_make_candidates(game, player):
    cue = game.P[0]
    cands = []
    for t in game.targets(player):
        tp = game.P[t]
        for k in range(6):
            v = bilhar_POCKETS[k] - tp
            dtp = float(np.linalg.norm(v))
            if dtp < 1e-6:
                continue
            u = v / dtp
            entry = float(u @ bilhar_AXES[k])
            if entry < 0.1:
                continue
            ghost = tp - u * 2 * bilhar_R
            a = ghost - cue
            dcg = float(np.linalg.norm(a))
            if dcg < 1e-6:
                continue
            cos = float(a @ u) / dcg
            if cos < 0.05:
                continue
            c1 = 0.0 if bilhar_blocked(game, cue, ghost, {0, t}) else 1.0
            c2 = 0.0 if bilhar_blocked(game, tp, bilhar_POCKETS[k], {0, t}) else 1.0
            corner = 1.0 if k in (0, 2, 3, 5) else 0.0
            ang = math.atan2(a[1], a[0])
            d, e = dcg / 900, dtp / 900
            for pw in bilhar_POWERS:
                f = [1, cos, cos * cos, d, e, c1, c2, corner, pw, pw * d, pw * e, pw * pw,
                     pw * (1 - cos), 1.0 if t == 8 else 0.0, entry, cos * c1 * c2, entry * c2]
                cands.append((f, ang, pw, k, t))
    if not cands:
        for t in game.targets(player):
            a = game.P[t] - cue
            d = float(np.linalg.norm(a)) / 900
            cands.append(([1, 0, 0, d, 0, 0, 0, 0, .5, .5 * d, 0, .25, .5, 1.0 if t == 8 else 0.0, 0, 0, 0],
                          math.atan2(a[1], a[0]), 0.5, 0, t))
    return cands


def bilhar_heuristic(X):
    cos, d, e, c1, c2, pw, entry = X[:, 1], X[:, 3], X[:, 4], X[:, 5], X[:, 6], X[:, 8], X[:, 14]
    want = np.clip(0.25 + 0.6 * (d + e), 0.3, 0.9)
    s = 3 * c1 + 3 * c2 + 5 * cos + 2 * entry - 3 * d - 3 * e - 6 * (pw - want) ** 2 - 2 * X[:, 12]
    return 0.6 * s


class bilhar_Policy:
    HIDDEN = (512, 1024, 2048, 1024, 512)

    def __init__(self, nh=None, seed=0):
        r = np.random.default_rng(seed)
        dims = (bilhar_NF,) + self.HIDDEN + (1,)
        self.weights = []
        self.biases = []
        for fan_in, fan_out in zip(dims[:-1], dims[1:]):
            # Xavier/Glorot: mantém as ativações tanh numa escala estável.
            scale = np.sqrt(1.0 / fan_in)
            self.weights.append(r.normal(0.0, scale, (fan_in, fan_out)).astype(np.float32))
            self.biases.append(np.zeros(fan_out, dtype=np.float32))
        self.fresh = True
        self.reset_opt()

    @property
    def W1(self):
        return self.weights[0]

    @property
    def b1(self):
        return self.biases[0]

    @property
    def w2(self):
        return self.weights[-1].reshape(-1)

    @property
    def b2(self):
        return float(self.biases[-1][0])

    def reset_opt(self):
        self.m = [np.zeros_like(x) for x in self.params()]
        self.v = [np.zeros_like(x) for x in self.params()]
        self.t = 0

    def params(self):
        out = []
        for w, b in zip(self.weights, self.biases):
            out.extend((w, b))
        return out

    def _forward(self, X):
        a = np.asarray(X, dtype=np.float32)
        activations = [a]
        preacts = []
        for w, b in zip(self.weights[:-1], self.biases[:-1]):
            z = a @ w + b
            preacts.append(z)
            a = np.tanh(z)
            activations.append(a)
        scores = (a @ self.weights[-1] + self.biases[-1]).reshape(-1)
        return scores, (activations, preacts)

    def scores(self, X):
        return self._forward(X)

    def act(self, X, temp=1.0, rng=None, greedy=False):
        s, cache = self.scores(X)
        rede = bilhar_rede_athena()
        if rede is not None and len(s) > 1 and rede.athena_ativo("bilhar"):
            vies = rede.athena_vies("bilhar", list(np.asarray(X, dtype=np.float32)), None)
            if vies is not None:
                s = s + 1.5 * np.asarray(vies, dtype=np.float32)
        z = s / max(float(temp), 1e-6)
        z = z - z.max()
        p = np.exp(z)
        p /= p.sum()
        i = int(np.argmax(p)) if greedy else int((rng or np.random.default_rng()).choice(len(p), p=p))
        if rede is not None:
            rede.athena_escolha("bilhar", np.asarray(X, dtype=np.float32)[i], None)
        return i, p, cache

    @staticmethod
    def _backward(pol, cache, ds):
        activations, preacts = cache
        ds = np.asarray(ds, dtype=np.float32).reshape(-1, 1)
        grads = [None] * (2 * len(pol.weights))
        # Camada de saída linear.
        grads[-2] = activations[-1].T @ ds
        grads[-1] = ds.sum(axis=0)
        da = ds @ pol.weights[-1].T
        # Camadas ocultas tanh, da última para a primeira.
        for layer in range(len(pol.weights) - 2, -1, -1):
            dz = da * (1.0 - np.tanh(preacts[layer]) ** 2)
            grads[2 * layer] = activations[layer].T @ dz
            grads[2 * layer + 1] = dz.sum(axis=0)
            if layer:
                da = dz @ pol.weights[layer].T
        return grads

    @staticmethod
    def _grad(pol, X, cache, p, i, A):
        ds = -float(A) * (np.eye(len(p), dtype=np.float32)[i] - p)
        return bilhar_Policy._backward(pol, cache, ds)

    def update(self, grads, lr=0.01):
        self.t += 1
        for n, (param, g, mm, vv) in enumerate(zip(self.params(), grads, self.m, self.v)):
            g = np.asarray(g, dtype=np.float32)
            mm *= 0.9
            mm += 0.1 * g
            vv *= 0.999
            vv += 0.001 * g * g
            mhat = mm / (1 - 0.9 ** self.t)
            vhat = vv / (1 - 0.999 ** self.t)
            param -= lr * mhat / (np.sqrt(vhat) + 1e-8)

    def save(self, path=bilhar_WEIGHTS):
        arrays = {}
        if os.path.exists(path):
            try:
                with np.load(path, allow_pickle=False) as old:
                    for key in old.files:
                        if key == "ATHENA_PROFILE":
                            arrays[key] = old[key]
            except Exception:
                pass
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            arrays[f"W{i}"] = w
            arrays[f"b{i}"] = b
        arrays["ATHENA_ARCH"] = np.asarray("17-512-1024-2048-1024-512-1")
        arrays["ATHENA_TRAINED"] = np.asarray(True)
        bilhar_guardar_npz(path, arrays)

    @classmethod
    def load(cls, path=None):
        path = path or bilhar_find_weights()
        pol = cls()
        pol.fresh = True
        if os.path.exists(path):
            try:
                with np.load(path, allow_pickle=False) as d:
                    expected = len(pol.weights)
                    if all(f"W{i}" in d.files and f"b{i}" in d.files for i in range(expected)):
                        if all(d[f"W{i}"].shape == pol.weights[i].shape and
                               d[f"b{i}"].shape == pol.biases[i].shape for i in range(expected)):
                            for i in range(expected):
                                pol.weights[i][...] = d[f"W{i}"]
                                pol.biases[i][...] = d[f"b{i}"]
                            pol.fresh = not (bool(d["ATHENA_TRAINED"].item()) if "ATHENA_TRAINED" in d.files else True)
                    # Compatibilidade com a versão antiga de uma camada:
                    elif "W1" in d.files and "b1" in d.files and "w2" in d.files:
                        if d["W1"].shape == (bilhar_NF, 32) and d["w2"].shape == (32,):
                            pol.weights[0][:, :32] = d["W1"]
                            pol.biases[0][:32] = d["b1"]
                            pol.fresh = True  # a rede nova ainda precisa de pré-treino
            except Exception:
                pass
        pol.reset_opt()
        return pol


def bilhar_random_state(rng):
    g = bilhar_Game(rng)
    g.on = rng.random(16) < rng.uniform(0.3, 1.0)
    g.on[0] = True
    pos = []
    for b in range(16):
        if not g.on[b]:
            continue
        for _ in range(60):
            q = np.array([rng.uniform(bilhar_L + bilhar_R, bilhar_RT - bilhar_R), rng.uniform(bilhar_T + bilhar_R, bilhar_B - bilhar_R)])
            if (np.linalg.norm(bilhar_POCKETS - q, axis=1) < bilhar_PR + bilhar_R).any():
                continue
            if all(np.linalg.norm(q - p) > 2 * bilhar_R + 1 for p in pos):
                break
        pos.append(q)
        g.P[b] = q
    m = rng.integers(3)
    g.groups = [[None, None], ["solid", "stripe"], ["stripe", "solid"]][m]
    g.shots = 1
    return g


def bilhar_pretrain(policy, rng, n=24, steps=12, lr=0.0015, verbose=True):
    Xs = []
    while len(Xs) < n:
        c = bilhar_make_candidates(bilhar_random_state(rng), 0)
        if c:
            Xs.append(np.asarray([x[0] for x in c], dtype=np.float32))
    X = np.vstack(Xs)
    Y = bilhar_heuristic(X).astype(np.float32)
    for step in range(steps):
        scores, cache = policy.scores(X)
        e = scores - Y
        ds = (2.0 * e / len(X)).astype(np.float32)
        grads = bilhar_Policy._backward(policy, cache, ds)
        policy.update(grads, lr)
        if verbose and step % 200 == 0:
            print(f"  pré-treino {step:4d}  erro {float((e ** 2).mean()):.4f}", flush=True)
    policy.reset_opt()
    policy.fresh = False


def bilhar_ai_place(game, player, policy, rng):
    best, best_s = None, -1e9
    for _ in range(40):
        pos = np.array([rng.uniform(bilhar_L + bilhar_R, (bilhar_HEAD[0] if game.kitchen else bilhar_RT) - bilhar_R), rng.uniform(bilhar_T + bilhar_R, bilhar_B - bilhar_R)])
        if not game.valid_spot(pos):
            continue
        old = game.P[0].copy()
        game.P[0] = pos
        c = bilhar_make_candidates(game, player)
        game.P[0] = old
        if c:
            s, _ = policy.scores(np.array([x[0] for x in c]))
            if s.max() > best_s:
                best, best_s = pos, s.max()
    game.P[0] = best if best is not None else bilhar_HEAD
    game.V[0] = 0


def bilhar_ai_pick(game, player, policy, rng, temp=1.0, greedy=False, noise=0.004):
    if game.shots == 0:
        a = bilhar_RACK - game.P[0]
        return math.atan2(a[1], a[0]) + rng.normal(0, 0.01), 0.95, (0.0, 0.0), None, None
    c = bilhar_make_candidates(game, player)
    X = np.array([x[0] for x in c])
    i, p, H = policy.act(X, temp, rng, greedy)
    _, ang, pw, k, _t = c[i]
    called = k if game.targets(player) == [8] else None
    return ang + rng.normal(0, noise), pw, (0.0, 0.0), called, (X, H, p, i)


def bilhar_value(g, res, player, policy):
    if g.over:
        return 50.0 if g.winner == player else -50.0
    v = res["good"] * 1.0 - (2.5 if res["foul"] else 0) - (1.5 if res["scratch"] else 0)
    if g.ball_in_hand:
        nxt_val = 6.0
    else:
        c = bilhar_make_candidates(g, g.turn)
        nxt_val = float(policy.scores(np.array([x[0] for x in c]))[0].max()) if c else -3.0
    return v + (0.4 if g.turn == player else -0.4) * nxt_val


def bilhar_extra_candidates(game, player, n_bank=4, n_kick=3):
    cue = game.P[0]
    walls = [(0, bilhar_L + bilhar_R), (0, bilhar_RT - bilhar_R), (1, bilhar_T + bilhar_R), (1, bilhar_B - bilhar_R)]

    def mirror(p, ax, v):
        q = p.copy()
        q[ax] = 2 * v - q[ax]
        return q

    banks, kicks = [], []
    for t in game.targets(player):
        tp = game.P[t]
        for ax, v in walls:
            for k in range(6):
                pm = mirror(bilhar_POCKETS[k], ax, v)
                dv = pm - tp
                dd = float(np.linalg.norm(dv))
                if dd < 1e-6:
                    continue
                u = dv / dd
                if abs(u[ax]) < 1e-9:
                    continue
                tt = (v - tp[ax]) / u[ax]
                if tt <= 0:
                    continue
                hp = tp + u * tt
                lo, hi = (bilhar_T + bilhar_R, bilhar_B - bilhar_R) if ax == 0 else (bilhar_L + bilhar_R, bilhar_RT - bilhar_R)
                if not (lo < hp[1 - ax] < hi):
                    continue
                ghost = tp - u * 2 * bilhar_R
                a = ghost - cue
                if np.linalg.norm(a) < 1e-6 or bilhar_blocked(game, cue, ghost, {0, t}):
                    continue
                banks.append((float(np.linalg.norm(a)) + dd, math.atan2(a[1], a[0]), k, t))
            tm = mirror(tp, ax, v)
            a = tm - cue
            u = a / max(float(np.linalg.norm(a)), 1e-9)
            if abs(u[ax]) < 1e-9:
                continue
            tt = (v - cue[ax]) / u[ax]
            if tt <= 0:
                continue
            hp = cue + u * tt
            lo, hi = (bilhar_T + bilhar_R, bilhar_B - bilhar_R) if ax == 0 else (bilhar_L + bilhar_R, bilhar_RT - bilhar_R)
            if lo < hp[1 - ax] < hi:
                kicks.append((float(np.linalg.norm(a)), math.atan2(a[1], a[0]), 0, t))
    banks.sort(key=lambda z: z[0])
    kicks.sort(key=lambda z: z[0])
    out = []
    for _, ang, k, t in banks[:n_bank]:
        out += [(ang, 0.6, k, t), (ang, 0.85, k, t)]
    for _, ang, k, t in kicks[:n_kick]:
        out += [(ang, 0.5, k, t), (ang, 0.8, k, t)]
    return out


def bilhar_sim(game, ang, pw, sp, called, player, policy, rng, noise):
    g = game.clone()
    g.start_shot(ang + (rng.normal(0, noise) if noise else 0.0), pw, sp, called)
    while g.step():
        pass
    return bilhar_value(g, g.end_shot(), player, policy)


def bilhar_ai_search(game, player, policy, rng, K=8, nb=4, nk=3, spin_top=0, refine=3, exec_noise=0.0015):
    c = bilhar_make_candidates(game, player)
    X = np.array([x[0] for x in c])
    s, _ = policy.scores(X)
    need8 = game.targets(player) == [8]
    pool = [(c[i][1], c[i][2], c[i][3] if need8 else None) for i in np.argsort(-s)[:K]]
    for ang, pw, k, _t in bilhar_extra_candidates(game, player, nb, nk):
        pool.append((ang, pw, k if need8 else None))
    z0 = (0.0, 0.0)
    scored = [[bilhar_sim(game, a, p, z0, cl, player, policy, rng, 0.0), a, p, z0, cl] for a, p, cl in pool]
    scored.sort(key=lambda z: -z[0])
    for v, a, p, sp, cl in list(scored[:spin_top]):
        for sp2 in ((0.0, -0.6), (0.0, 0.6)):
            scored.append([bilhar_sim(game, a, p, sp2, cl, player, policy, rng, 0.0), a, p, sp2, cl])
    scored.sort(key=lambda z: -z[0])
    top = scored[:refine]
    for z in top:
        vs = [z[0]] + [bilhar_sim(game, z[1], z[2], z[3], z[4], player, policy, rng, 0.003) for _ in range(2)]
        z[0] = float(np.mean(vs))
    best = max(top, key=lambda z: z[0])
    return best[1] + rng.normal(0, exec_noise), best[2], best[3], best[4]


# IA v2: geometria + pesquisa por simulação com a física real.
#   - tacadas diretas, por 1 e 2 tabelas, combinações, "kicks" e DEFESA (prender o adversário)
#   - efeito (segue / recua / lateral) para controlar a posição da branca
#   - avaliação da "deixa": ameaça do adversário, snooker, qualidade da mesa
#   - tacadas confirmadas com ruído e pesquisa a 2 jogadas (simula a melhor resposta do adversário)
#   - bola na mão: escolhe o melhor ponto da mesa; abertura: simula e escolhe a melhor
import time

bilhar_LAM = -math.log(bilhar_FR)                  # perda de velocidade por unidade de distância (~0.0151)
bilhar_LO_X, bilhar_HI_X, bilhar_LO_Y, bilhar_HI_Y = bilhar_L + bilhar_R, bilhar_RT - bilhar_R, bilhar_T + bilhar_R, bilhar_B - bilhar_R
bilhar_THETAS = np.linspace(-1.2, 1.2, 13)
bilhar_THETAS9 = np.linspace(-1.15, 1.15, 9)
bilhar_WALLS = [(0, bilhar_LO_X), (0, bilhar_HI_X), (1, bilhar_LO_Y), (1, bilhar_HI_Y)]
bilhar_SPINS = [(0.0, 0.6), (0.0, -0.6), (0.0, 1.0), (0.0, -1.0), (0.7, 0.0), (-0.7, 0.0)]
bilhar_BUDGET_SCALE = 1.0

bilhar_LEVEL_CFG = {
    "normal":  dict(budget=2.0, n_direct=6, n_bank=3, n_combo=2, n_kick=2, n_safe=4, tgt_safe=2,
                    spin_top=1, noisy=2, two_ply=0, exec_noise=0.0015),
    "dificil": dict(budget=4.5, n_direct=10, n_bank=6, n_combo=4, n_kick=3, n_safe=8, tgt_safe=3,
                    spin_top=3, noisy=3, two_ply=3, exec_noise=0.0006),
    "mestre":  dict(budget=9.0, n_direct=14, n_bank=10, n_combo=6, n_kick=4, n_safe=12, tgt_safe=4,
                    spin_top=5, noisy=4, two_ply=5, exec_noise=0.0002),
}
bilhar_KIND_TXT = {"direta": "tacada direta", "tabela1": "tacada por tabela", "tabela2": "tacada por duas tabelas",
            "combo": "combinação", "kick": "tabela para chegar à bola", "defesa": "defesa - a prender-te",
            "abertura": "abertura"}


def bilhar_in_play(q, m=2.0):
    return bilhar_LO_X - m <= q[0] <= bilhar_HI_X + m and bilhar_LO_Y - m <= q[1] <= bilhar_HI_Y + m


def bilhar_blocked_many(game, a, ends, exclude):
    ids = [i for i in range(16) if game.on[i] and i not in exclude]
    if not ids:
        return np.zeros(len(ends), bool)
    p = game.P[ids]
    ab = ends - a
    l2 = np.maximum((ab * ab).sum(1), 1e-9)
    t = np.clip(((p[None] - a) * ab[:, None]).sum(-1) / l2[:, None], 0, 1)
    proj = a + t[..., None] * ab[:, None]
    d = np.linalg.norm(p[None] - proj, axis=-1)
    return (d < 2 * bilhar_R * 0.98).any(1)


def bilhar_pot_prob(game, cue, t, k):
    tp = game.P[t]
    v = bilhar_POCKETS[k] - tp
    dtp = float(math.hypot(v[0], v[1]))
    if dtp < 1e-6:
        return 0.0
    u = v / dtp
    entry = float(u @ bilhar_AXES[k])
    if entry < 0.15:
        return 0.0
    ghost = tp - u * 2 * bilhar_R
    if not bilhar_in_play(ghost):
        return 0.0
    if bilhar_blocked(game, tp, bilhar_POCKETS[k], {0, t}):
        return 0.0
    if cue is None:
        dcg, pc = 300.0, 0.8
    else:
        a = ghost - cue
        dcg = float(math.hypot(a[0], a[1]))
        if dcg < 1e-6:
            return 0.0
        cos = float(a @ u) / dcg
        if cos < 0.12:
            return 0.0
        if bilhar_blocked(game, cue, ghost, {0, t}):
            return 0.0
        pc = math.exp(-(math.acos(min(1.0, cos)) / 0.85) ** 2)
    pe = min(1.0, max(0.05, (entry - 0.12) / 0.5)) ** 0.6
    return 0.98 * pc * pe * math.exp(-(dcg + dtp) / 1500.0) * (0.92 if k in (1, 4) else 1.0)


def bilhar_best_pot(game, player, cue):
    best = (0.0, None, None)
    for t in game.targets(player):
        for k in range(6):
            p = bilhar_pot_prob(game, cue, t, k)
            if p > best[0]:
                best = (p, t, k)
    return best


def bilhar_table_quality(game, player):
    tg = game.targets(player)
    if not tg:
        return 0.0
    ps = np.array([max(bilhar_pot_prob(game, None, t, k) for k in range(6)) for t in tg])
    if len(ps) == 1:
        return float(ps[0])
    return float(0.7 * ps.mean() + 0.3 * ps.min())


def bilhar_reach_of(game, cue, targets):
    best = 0.0
    for t in targets:
        tp = game.P[t]
        w = cue - tp
        if math.hypot(w[0], w[1]) < 1e-6:
            continue
        ang = math.atan2(w[1], w[0]) + bilhar_THETAS
        ends = tp + 2 * bilhar_R * np.stack([np.cos(ang), np.sin(ang)], 1)
        inb = (ends[:, 0] >= bilhar_LO_X - 2) & (ends[:, 0] <= bilhar_HI_X + 2) & (ends[:, 1] >= bilhar_LO_Y - 2) & (ends[:, 1] <= bilhar_HI_Y + 2)
        free = (~bilhar_blocked_many(game, cue, ends, {0, t})) & inb
        best = max(best, float(free.mean()))
    return best


def bilhar_threat(game, opp):
    tg = game.targets(opp)
    if not tg:
        return 0.0, 1.0
    w8 = 6.0 if tg == [8] else 1.0
    tq = bilhar_table_quality(game, opp)
    if game.ball_in_hand:
        p1 = min(0.97, 1.15 * max(max(bilhar_pot_prob(game, None, t, k) for k in range(6)) for t in tg))
        return w8 * p1 * (1 + 0.6 * tq), 1.0
    cue = game.P[0]
    p1 = bilhar_best_pot(game, opp, cue)[0]
    reach = bilhar_reach_of(game, cue, tg)
    return w8 * max(p1 * (1 + 0.6 * tq), 0.10 + 0.15 * reach), reach


def bilhar_value_parts(g, res, player):
    if g.over:
        return (60.0 if g.winner == player else -60.0), None
    opp = 1 - player
    v = float(res["good"])
    og = g.groups[opp]
    if og:
        v -= 0.9 * sum(1 for b in g.pocketed if b and bilhar_group_of(b) == og)
    if res["foul"]:
        v -= 2.0
    if res["scratch"]:
        v -= 0.5
    if g.turn == player and not g.ball_in_hand:
        tg = g.targets(player)
        p1 = bilhar_best_pot(g, player, g.P[0])[0]
        w8 = 6.0 if tg == [8] else 1.0
        v += 1.1 * w8 * max(p1, 0.25) * (1 + 0.6 * bilhar_table_quality(g, player))
        return v, None
    thr, reach = bilhar_threat(g, opp)
    part = -1.25 * thr + 0.45 * (1 - reach)       # deixa difícil / snooker => bom para mim
    v += part + 0.35 * bilhar_table_quality(g, player)
    return v, part


def bilhar_run(g, ang, pw, sp, called):
    g.start_shot(ang, pw, sp, called)
    n = 0
    while g.step():
        n += 1
        if n > 3000:
            break
    return g.end_shot()


def bilhar_state_of(g):
    d = dict(g.__dict__)
    d.pop("rng", None)
    return d


def bilhar_from_state(d):
    g = bilhar_Game.__new__(bilhar_Game)
    g.__dict__.update(d)
    g.rng = None
    g.P, g.V, g.on = g.P.copy(), g.V.copy(), g.on.copy()
    g.groups, g.pocketed = list(g.groups), list(g.pocketed)
    g.pocket_of, g.rail_balls = dict(g.pocket_of), set(g.rail_balls)
    g.spin, g.cue_dir = g.spin.copy(), g.cue_dir.copy()
    return g


def bilhar_task(args):
    st, ang, pw, sp, called, player, noise, seed = args
    g = bilhar_from_state(st)
    if noise:
        ang = ang + float(np.random.default_rng(seed).normal(0, noise))
    res = bilhar_run(g, ang, pw, sp, called)
    return bilhar_value_parts(g, res, player)[0]


def bilhar_ping(_):
    return 1


class bilhar_Evaluator:

    def __init__(self, workers=0):
        self.pool, self.n = None, 1
        if workers and workers > 1:
            try:
                import multiprocessing as mp
                from concurrent.futures import ProcessPoolExecutor
                self.pool = ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn"))
                list(self.pool.map(bilhar_ping, range(workers)))
                self.n = workers
            except Exception:
                self.pool = None

    def close(self):
        if self.pool is not None:
            try:
                self.pool.shutdown(wait=True, cancel_futures=True)
            except Exception:
                pass

    def values(self, game, specs, player, noise=0.0, seed0=0, deadline=None):
        out = [None] * len(specs)
        st = bilhar_state_of(game)
        tasks = [(st, s[0], s[1], s[2], s[3], player, noise, seed0 + i) for i, s in enumerate(specs)]
        if self.pool is not None:
            try:
                bs = self.n * 2
                for i in range(0, len(tasks), bs):
                    if deadline and i > 0 and time.time() > deadline:
                        break
                    for j, v in enumerate(self.pool.map(bilhar_task, tasks[i:i + bs])):
                        out[i + j] = v
                return out
            except Exception:
                self.pool, self.n = None, 1
        for i, tk in enumerate(tasks):
            if out[i] is not None:
                continue
            if deadline and i > 0 and time.time() > deadline:
                break
            out[i] = bilhar_task(tk)
        return out


bilhar_SERIAL = bilhar_Evaluator(0)


def bilhar_reflect(p, ax, v):
    q = np.array(p, float)
    q[ax] = 2 * v - q[ax]
    return q


def bilhar_trace_bounces(start, d, nb):
    pos = np.array(start, float)
    pts = [pos.copy()]
    d = np.array(d, float)
    for _ in range(nb):
        best, bax = 1e18, None
        for ax, lo, hi in ((0, bilhar_LO_X, bilhar_HI_X), (1, bilhar_LO_Y, bilhar_HI_Y)):
            if abs(d[ax]) < 1e-9:
                continue
            tt = ((hi if d[ax] > 0 else lo) - pos[ax]) / d[ax]
            if 1e-6 < tt < best:
                best, bax = tt, ax
        if bax is None:
            return pts, d
        pos = pos + d * best
        d = d.copy()
        d[bax] = -d[bax]
        pts.append(pos.copy())
    return pts, d


def bilhar_bounce_dirs(src, dst, nb):
    out = []
    seqs = [[w] for w in bilhar_WALLS] if nb == 1 else [[a, b] for a in bilhar_WALLS for b in bilhar_WALLS if a != b]
    for seq in seqs:
        img = np.array(dst, float)
        for ax, v in reversed(seq):
            img = bilhar_reflect(img, ax, v)
        d = img - src
        n = float(math.hypot(d[0], d[1]))
        if n < 1e-6:
            continue
        d = d / n
        pts, dend = bilhar_trace_bounces(src, d, nb)
        if len(pts) != nb + 1:
            continue
        w = np.array(dst, float) - pts[-1]
        tproj = float(w @ dend)
        if tproj <= 0:
            continue
        out.append((d, pts, float(abs(w[0] * dend[1] - w[1] * dend[0])), tproj))
    return out


def bilhar_power_for(dcg, dobj, nb=0, cosv=1.0):
    v_obj = bilhar_LAM * dobj / (bilhar_E_RAIL ** nb) * 1.05 + 1.2
    v_c = v_obj / (0.975 * max(cosv, 0.25))
    return float(np.clip((v_c + bilhar_LAM * dcg) / bilhar_MAXV, 0.22, 1.0))


def bilhar_direct_candidates(game, player, policy, n):
    c = bilhar_make_candidates(game, player)
    if not c:
        return []
    X = np.array([x[0] for x in c])
    s, _ = policy.scores(X)
    need8 = game.targets(player) == [8]
    feas = X[:, 5] * X[:, 6]
    order = np.lexsort((-s, -feas))
    out, seen = [], {}
    for i in order:
        f, ang, pw, k, t = c[i]
        key = (t, k)
        if seen.get(key, 0) >= 2:
            continue
        seen[key] = seen.get(key, 0) + 1
        out.append((ang, pw, (0.0, 0.0), k if need8 else None, "direta"))
        if len(out) >= n:
            break
    return out


def bilhar_bank_candidates(game, player, n, max_nb=2):
    cue = game.P[0]
    need8 = game.targets(player) == [8]
    found = []
    for t in game.targets(player):
        tp = game.P[t]
        for k in range(6):
            for nb in range(1, max_nb + 1):
                for d, pts, dist, tproj in bilhar_bounce_dirs(tp, bilhar_POCKETS[k], nb):
                    if dist > bilhar_PR[k] * 0.6:
                        continue
                    ghost = tp - d * 2 * bilhar_R
                    if not bilhar_in_play(ghost):
                        continue
                    a = ghost - cue
                    dcg = float(math.hypot(a[0], a[1]))
                    if dcg < 1e-6 or float(a @ d) / dcg < 0.15 or bilhar_blocked(game, cue, ghost, {0, t}):
                        continue
                    if any(bilhar_blocked(game, pts[i], pts[i + 1], {0, t}) for i in range(len(pts) - 1)):
                        continue
                    if bilhar_blocked(game, pts[-1], bilhar_POCKETS[k], {0, t}):
                        continue
                    plen = sum(float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(len(pts) - 1)) + tproj
                    found.append((dcg + plen + 250 * (nb - 1), math.atan2(a[1], a[0]), k, nb, plen, dcg, float(a @ d) / dcg))
    found.sort(key=lambda z: z[0])
    out, seen = [], set()
    for cost, ang, k, nb, plen, dcg, cosv in found:
        if (round(ang, 3), k) in seen:
            continue
        seen.add((round(ang, 3), k))
        pw = bilhar_power_for(dcg, plen, nb, cosv)
        called = k if need8 else None
        out.append((ang, pw, (0.0, 0.0), called, f"tabela{nb}"))
        out.append((ang, min(1.0, pw * 1.3), (0.0, 0.0), called, f"tabela{nb}"))
        if len(out) >= 2 * n:
            break
    return out


def bilhar_combo_candidates(game, player, n):
    cue = game.P[0]
    tg = game.targets(player)
    found = []
    for b in tg:
        bp = game.P[b]
        for t in tg:
            if t == b:
                continue
            tp = game.P[t]
            for k in range(6):
                v = bilhar_POCKETS[k] - tp
                dtp = float(math.hypot(v[0], v[1]))
                if dtp < 1e-6:
                    continue
                u = v / dtp
                if float(u @ bilhar_AXES[k]) < 0.2:
                    continue
                g = tp - u * 2 * bilhar_R
                if not bilhar_in_play(g):
                    continue
                w = g - bp
                dw = float(math.hypot(w[0], w[1]))
                if dw < 1e-6:
                    continue
                w = w / dw
                if float(w @ u) < 0.15:
                    continue
                gb = bp - w * 2 * bilhar_R
                if not bilhar_in_play(gb):
                    continue
                a = gb - cue
                dcg = float(math.hypot(a[0], a[1]))
                if dcg < 1e-6:
                    continue
                cosb = float(a @ w) / dcg
                if cosb < 0.2:
                    continue
                if bilhar_blocked(game, cue, gb, {0, b}) or bilhar_blocked(game, bp, g, {0, b, t}) \
                        or bilhar_blocked(game, tp, bilhar_POCKETS[k], {0, b, t}):
                    continue
                found.append((dcg + dw + dtp + 300 * (1 - cosb), math.atan2(a[1], a[0]), dcg, dw + dtp, cosb))
    found.sort(key=lambda z: z[0])
    out = []
    for cost, ang, dcg, dobj, cosb in found[:n]:
        pw = bilhar_power_for(dcg, dobj * 1.2, 0, cosb * 0.8)
        out.append((ang, pw, (0.0, 0.0), None, "combo"))
        out.append((ang, min(1.0, pw * 1.25), (0.0, 0.0), None, "combo"))
    return out


def bilhar_kick_candidates(game, player, n, max_nb=2):
    cue = game.P[0]
    need8 = game.targets(player) == [8]
    found = []
    for t in game.targets(player):
        tp = game.P[t]
        for nb in range(1, max_nb + 1):
            for d, pts, dist, tproj in bilhar_bounce_dirs(cue, tp, nb):
                if dist > bilhar_R * 0.7:
                    continue
                if any(bilhar_blocked(game, pts[i], pts[i + 1], {0, t}) for i in range(len(pts) - 1)):
                    continue
                if bilhar_blocked(game, pts[-1], tp, {0, t}):
                    continue
                length = sum(float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(len(pts) - 1)) + tproj
                found.append((length + 200 * (nb - 1), math.atan2(d[1], d[0]), t, nb, length))
    found.sort(key=lambda z: z[0])
    out = []
    for cost, ang, t, nb, length in found[:n]:
        v0 = bilhar_LAM * length / (bilhar_E_RAIL ** nb) * 1.1 + 2.5
        called = int(np.argmin(np.linalg.norm(bilhar_POCKETS - game.P[t], axis=1))) if need8 else None
        for f in (1.0, 1.4):
            out.append((ang, float(np.clip(v0 * f / bilhar_MAXV, 0.25, 0.95)), (0.0, 0.0), called, "kick"))
    return out


def bilhar_roll_out(pos, vel, maxb=3):
    sp = float(math.hypot(vel[0], vel[1]))
    pos = np.array(pos, float)
    if sp < 1e-6:
        return pos, False
    d = np.array(vel, float) / sp
    budget = sp / bilhar_LAM
    touched = False
    for _ in range(maxb + 1):
        best, bax = 1e18, None
        for ax, lo, hi in ((0, bilhar_LO_X, bilhar_HI_X), (1, bilhar_LO_Y, bilhar_HI_Y)):
            if abs(d[ax]) < 1e-9:
                continue
            tt = ((hi if d[ax] > 0 else lo) - pos[ax]) / d[ax]
            if tt > 1e-6 and tt < best:
                best, bax = tt, ax
        if bax is None or budget <= best:
            return pos + d * (budget if bax is None else min(budget, best)), touched
        pos = pos + d * best
        budget = (budget - best) * bilhar_E_RAIL
        d = d.copy()
        d[bax] = -d[bax]
        touched = True
    return pos, touched


def bilhar_safety_candidates(game, player, n, targets_max=3):
    cue = game.P[0]
    opp = 1 - player
    tgs = sorted(game.targets(player), key=lambda t: float(np.linalg.norm(game.P[t] - cue)))[:targets_max]
    scored = []
    for t in tgs:
        tp = game.P[t]
        w = cue - tp
        base = math.atan2(w[1], w[0])
        for th in bilhar_THETAS9:
            g = tp + 2 * bilhar_R * np.array([math.cos(base + th), math.sin(base + th)])
            if not bilhar_in_play(g) or bilhar_blocked(game, cue, g, {0, t}):
                continue
            a = g - cue
            dcg = float(math.hypot(a[0], a[1]))
            if dcg < 1e-6:
                continue
            dirv = a / dcg
            nn = (tp - g) / (2 * bilhar_R)
            cph = float(dirv @ nn)
            if cph < 0.05:
                continue
            for pw in (0.22, 0.34, 0.5):
                vc = pw * bilhar_MAXV - bilhar_LAM * dcg
                if vc < 0.6:
                    continue
                vn = vc * cph
                qc, tc = bilhar_roll_out(g, vc * dirv - 0.975 * vn * nn)
                qo, to = bilhar_roll_out(tp, 0.975 * vn * nn)
                if not (tc or to):
                    continue
                if (np.linalg.norm(bilhar_POCKETS - qc, axis=1) < bilhar_PR + bilhar_R * 0.5).any():
                    continue
                if (np.linalg.norm(bilhar_POCKETS - qo, axis=1) < bilhar_PR + 2).any():
                    continue
                o0, ot = game.P[0].copy(), game.P[t].copy()
                game.P[0], game.P[t] = qc, qo
                thr, reach = bilhar_threat(game, opp)
                game.P[0], game.P[t] = o0, ot
                scored.append((thr - 0.5 * (1 - reach), math.atan2(a[1], a[0]), pw))
    scored.sort(key=lambda z: z[0])
    out, seen = [], set()
    for sc, ang, pw in scored:
        key = (round(ang, 2), pw)
        if key in seen:
            continue
        seen.add(key)
        out.append((ang, pw, (0.0, 0.0), None, "defesa"))
        if len(out) >= n:
            break
    return out


def bilhar_ai_place2(game, player, rng):
    tg = game.targets(player)
    nxt = {}
    for t in tg:
        game.on[t] = False
        nxt[t] = bilhar_best_pot(game, player, game.P[t])[0] if game.targets(player) else 0.0
        game.on[t] = True
    viable = []
    for t in tg:
        tp = game.P[t]
        for k in range(6):
            v = bilhar_POCKETS[k] - tp
            dtp = float(math.hypot(v[0], v[1]))
            if dtp < 1e-6:
                continue
            u = v / dtp
            entry = float(u @ bilhar_AXES[k])
            ghost = tp - u * 2 * bilhar_R
            if entry < 0.15 or not bilhar_in_play(ghost) or bilhar_blocked(game, tp, bilhar_POCKETS[k], {0, t}):
                continue
            pe = min(1.0, max(0.05, (entry - 0.12) / 0.5)) ** 0.6 * (0.92 if k in (1, 4) else 1.0)
            viable.append((t, ghost, u, dtp, pe, nxt[t]))
    xmax = bilhar_HEAD[0] if game.kitchen else bilhar_RT - bilhar_R
    best, best_s = None, -1.0
    xs = np.linspace(bilhar_L + bilhar_R + 4, xmax - 2, 14)
    ys = np.linspace(bilhar_T + bilhar_R + 4, bilhar_B - bilhar_R - 4, 8)
    for x in xs:
        for y in ys:
            pos = np.array([x, y])
            if not game.valid_spot(pos):
                continue
            sc = 0.0
            for t, ghost, u, dtp, pe, nx in viable:
                a = ghost - pos
                dcg = float(math.hypot(a[0], a[1]))
                if dcg < 1e-6:
                    continue
                cos = float(a @ u) / dcg
                if cos < 0.12 or bilhar_blocked(game, pos, ghost, {0, t}):
                    continue
                p = 0.98 * math.exp(-(math.acos(min(1.0, cos)) / 0.85) ** 2) * pe * math.exp(-(dcg + dtp) / 1500.0)
                sc = max(sc, p * (1 + 0.7 * nx))
            if sc > best_s:
                best, best_s = pos, sc
    if best is None or best_s < 0.05:          # sem tacada limpa: maximiza o alcance
        alt, alt_s = None, -1.0
        for _ in range(40):
            pos = np.array([rng.uniform(bilhar_L + bilhar_R, xmax), rng.uniform(bilhar_T + bilhar_R, bilhar_B - bilhar_R)])
            if not game.valid_spot(pos):
                continue
            s_ = bilhar_reach_of(game, pos, tg)
            if s_ > alt_s:
                alt, alt_s = pos, s_
        if alt is not None:
            best = alt
    game.P[0] = best if best is not None else bilhar_HEAD.copy()
    game.V[0] = 0


def bilhar_key(s):
    return (round(s[0], 4), round(s[1], 2), s[2])


def bilhar_interleave(lists):
    out, i = [], 0
    while any(i < len(l) for l in lists):
        for l in lists:
            if i < len(l):
                out.append(l[i])
        i += 1
    return out


def bilhar_best_reply(g, player, policy, rng, ev, deadline=None):
    opp = 1 - player
    if g.over or not g.targets(opp):
        return 0.0
    g2 = g.clone()
    if g2.ball_in_hand:
        bilhar_ai_place2(g2, opp, rng)
        g2.ball_in_hand = False
    specs = bilhar_direct_candidates(g2, opp, policy, 5) + bilhar_bank_candidates(g2, opp, 2) \
        + bilhar_kick_candidates(g2, opp, 2) + bilhar_safety_candidates(g2, opp, 3, 2)
    if not specs:
        return -1.0
    vals = [v for v in ev.values(g2, [s[:4] for s in specs], opp, deadline=deadline) if v is not None]
    return max(vals) if vals else 0.0


def bilhar_ai_search2(game, player, policy, rng, ev, cfg, hint=None):
    t0 = time.time()
    budget = cfg["budget"] * bilhar_BUDGET_SCALE
    when = lambda f: t0 + budget * f
    pool = bilhar_interleave([
        bilhar_direct_candidates(game, player, policy, cfg["n_direct"]),
        bilhar_bank_candidates(game, player, cfg["n_bank"]),
        bilhar_combo_candidates(game, player, cfg["n_combo"]),
        bilhar_safety_candidates(game, player, cfg["n_safe"], cfg["tgt_safe"]),
        bilhar_kick_candidates(game, player, cfg["n_kick"]),
    ])
    seen, uniq = set(), []
    for s in pool:
        if bilhar_key(s) not in seen:
            seen.add(bilhar_key(s))
            uniq.append(s)
    pool = uniq
    if not pool:
        tp = game.P[game.targets(player)[0]]
        a = tp - game.P[0]
        return math.atan2(a[1], a[0]), 0.5, (0.0, 0.0), None, "direta"
    vals = ev.values(game, [s[:4] for s in pool], player, deadline=when(0.45))
    cands = [[s[:4], s[4], v] for s, v in zip(pool, vals) if v is not None]
    cands.sort(key=lambda c: -c[2])
    if hint:
        hint(cands[0][0][0])
    # efeito (segue / recua / lateral) nas melhores tacadas de pontaria
    base = [c for c in cands if c[1] != "defesa"][:cfg["spin_top"]]
    sp_specs, sp_kind = [], []
    for c in base:
        for sp in bilhar_SPINS:
            sp_specs.append((c[0][0], c[0][1], sp, c[0][3]))
            sp_kind.append(c[1])
    if sp_specs:
        for s, kd, v in zip(sp_specs, sp_kind, ev.values(game, sp_specs, player, deadline=when(0.6))):
            if v is not None:
                cands.append([s, kd, v])
        cands.sort(key=lambda c: -c[2])
        if hint:
            hint(cands[0][0][0])
    top = cands[:max(cfg["noisy"], cfg["two_ply"], 1)]
    # robustez: repete com ruído de execução
    if cfg["noisy"] > 0:
        reps = 3
        specs = [c[0] for c in top[:cfg["noisy"]] for _ in range(reps)]
        vs = ev.values(game, specs, player, noise=0.003, seed0=int(rng.integers(1 << 30)), deadline=when(0.72))
        for i, c in enumerate(top[:cfg["noisy"]]):
            part = [v for v in vs[i * reps:(i + 1) * reps] if v is not None]
            c.append(0.5 * c[2] + 0.5 * float(np.mean(part)) if part else c[2])
    for c in top:
        if len(c) == 3:
            c.append(c[2])
    # pesquisa a 2 jogadas: simula a melhor resposta do adversário nas melhores linhas
    top.sort(key=lambda c: -c[3])
    for n_, c in enumerate(top[:cfg["two_ply"]]):
        if n_ > 0 and time.time() > when(1.0):
            break
        g = game.clone()
        res = bilhar_run(g, c[0][0], c[0][1], c[0][2], c[0][3])
        tot, part = bilhar_value_parts(g, res, player)
        if part is None or g.over:
            continue
        reply = bilhar_best_reply(g, player, policy, rng, ev)
        c[3] = c[3] - part - 1.0 * reply
        if hint:
            hint(c[0][0])
    best = max(top, key=lambda c: c[3])
    (ang, pw, sp, called), kind = best[0], best[1]
    return ang + float(rng.normal(0, cfg["exec_noise"])), pw, sp, called, kind


def bilhar_ai_break(game, player, ev):
    base = math.atan2(*(bilhar_RACK - game.P[0])[::-1])
    offs = np.linspace(-0.09, 0.09, 13)
    stages = [
        [(base + o, pw, sp, None) for pw in (0.7, 0.8, 0.9) for o in offs for sp in ((0.0, 0.0), (0.0, 0.7))],
        [(base + o, pw, sp, None) for pw in (0.8, 1.0) for o in offs for sp in ((0.0, -0.7), (0.8, 0.0), (-0.8, 0.0))],
    ]
    best, best_v = None, -1e9
    for specs in stages:
        vals = ev.values(game, specs, player)
        for sp_, v in zip(specs, vals):
            if v is not None and v > best_v:
                best, best_v = sp_, v
        if best_v > -2.0:               # já há uma abertura legal
            break
    return best


bilhar_LEVELS = {"facil": 0, "normal": 1, "dificil": 2, "mestre": 3}


def bilhar_ai_think(game, player, policy, level, rng, ev=None, hint=None):
    g = game
    ev = ev or bilhar_SERIAL
    place = None
    if g.ball_in_hand:
        if level == "facil":
            bilhar_ai_place(g, player, policy, rng)
        else:
            bilhar_ai_place2(g, player, rng)
        place = g.P[0].copy()
        g.ball_in_hand = False
    if g.shots == 0:
        if level == "facil":
            ang, pw, sp, called, _ = bilhar_ai_pick(g, player, policy, rng)
        else:
            ang, pw, sp, called = bilhar_ai_break(g, player, ev)
        return place, ang, pw, sp, called, "abertura"
    if level == "facil":
        ang, pw, sp, called, _ = bilhar_ai_pick(g, player, policy, rng, temp=1.2, noise=0.03)
        return place, ang, pw, sp, called, "direta"
    if level == "antigo":                 # só para comparar com a versão anterior (torneio)
        ang, pw, sp, called = bilhar_ai_search(g, player, policy, rng, K=12, nb=6, nk=4,
                                        spin_top=4, refine=4, exec_noise=0.0005)
        return place, ang, pw, sp, called, "direta"
    ang, pw, sp, called, kind = bilhar_ai_search2(g, player, policy, rng, ev, bilhar_LEVEL_CFG[level], hint)
    return place, ang, pw, sp, called, kind


def bilhar_match(level_a, level_b, games=4, seed=0, max_shots=150, ev=None, verbose=True):
    rng = np.random.default_rng(seed)
    policy = bilhar_Policy.load()
    if policy.fresh:
        bilhar_pretrain(policy, rng, verbose=False)
        policy.save()
    ev = ev or bilhar_SERIAL
    wins = {level_a: 0, level_b: 0}
    kinds = {level_a: {}, level_b: {}}
    for gi in range(games):
        g = bilhar_Game(rng)
        lv = [level_a, level_b] if gi % 2 == 0 else [level_b, level_a]
        t0 = time.time()
        while not g.over and g.shots < max_shots:
            pl = g.turn
            place, ang, pw, sp, called, kind = bilhar_ai_think(g.clone(), pl, policy, lv[pl], rng, ev)
            kinds[lv[pl]][kind] = kinds[lv[pl]].get(kind, 0) + 1
            if place is not None:
                g.P[0], g.ball_in_hand = place, False
            g.start_shot(ang, pw, sp, called)
            while g.step():
                pass
            g.end_shot()
        w = lv[g.winner] if g.over else None
        if w:
            wins[w] += 1
        if verbose:
            print(f"jogo {gi + 1}: {lv[0]} (abre) vs {lv[1]} -> vencedor: {w or 'ninguém'} "
                  f"em {g.shots} tacadas ({time.time() - t0:.0f}s)", flush=True)
    if verbose:
        print("RESULTADO:", wins)
        for k, v in kinds.items():
            print("  tipos de tacada de", k, v)
    return wins, kinds


# Treino (auto-jogo, REINFORCE com Adam)
def bilhar_play_game(policy, rng, max_shots=60, temp=1.0):
    g = bilhar_Game(rng)
    traj = {0: [], 1: []}
    stats = {"good": 0, "fouls": 0}
    while not g.over and g.shots < max_shots:
        pl = g.turn
        if g.ball_in_hand:
            bilhar_ai_place(g, pl, policy, rng)
            g.ball_in_hand = False
        ang, pw, sp, called, info = bilhar_ai_pick(g, pl, policy, rng, temp)
        g.start_shot(ang, pw, sp, called)
        while g.step():
            pass
        res = g.end_shot()
        r = res["good"] - 0.5 * res["foul"] - 0.5 * res["scratch"] - 0.02
        stats["good"] += res["good"]
        stats["fouls"] += res["foul"]
        if info is not None:
            traj[pl].append([info, r])
    if g.over:
        for p in (0, 1):
            if traj[p]:
                traj[p][-1][1] += 5.0 if g.winner == p else -5.0
    return g, traj, stats


def bilhar_train(games=500, reset=False, batch=8, lr=0.004, gamma=0.95):
    policy = bilhar_Policy.load()
    rng = np.random.default_rng()
    if reset or policy.fresh:
        policy = bilhar_Policy()
        print("A pré-treinar a rede...")
        bilhar_pretrain(policy, rng)
        policy.save()
    buf, win = [], {"shots": 0, "good": 0, "fouls": 0, "fin": 0, "n": 0}
    try:
        for ep in range(1, games + 1):
            g, traj, st = bilhar_play_game(policy, rng)
            win["shots"] += g.shots; win["good"] += st["good"]; win["fouls"] += st["fouls"]
            win["fin"] += g.over; win["n"] += 1
            for p in (0, 1):
                G = 0.0
                for info, r in reversed(traj[p]):
                    G = r + gamma * G
                    buf.append((info, G))
            if ep % batch == 0 and buf:
                Gs = np.array([G for _, G in buf])
                adv = (Gs - Gs.mean()) / (Gs.std() + 1e-6)
                grads = None
                for ((X, H, p, i), _), A in zip(buf, adv):
                    gr = bilhar_Policy._grad(policy, X, H, p, i, A)
                    grads = gr if grads is None else [a + b for a, b in zip(grads, gr)]
                policy.update([x / len(buf) for x in grads], lr)
                buf = []
            if ep % 20 == 0:
                n = win["n"]
                print(f"jogo {ep:5d} | bolas/tacada {win['good'] / max(win['shots'], 1):.3f} | "
                      f"faltas/tacada {win['fouls'] / max(win['shots'], 1):.3f} | "
                      f"jogos terminados {100 * win['fin'] / n:.0f}% | tacadas/jogo {win['shots'] / n:.1f}", flush=True)
                win = {k: 0 for k in win}
                policy.save()
    except KeyboardInterrupt:
        print("Treino interrompido.")
    policy.save()
    print("Pesos guardados em", bilhar_WEIGHTS)


# Interface gráfica (pygame)
bilhar_COLORS = {1: (245, 200, 0), 2: (20, 70, 200), 3: (220, 35, 35), 4: (110, 35, 150),
          5: (245, 120, 10), 6: (0, 130, 55), 7: (130, 25, 25), 8: (20, 20, 20)}
bilhar_LEVEL_KEYS = ["facil", "normal", "dificil", "mestre"]


def bilhar_lerp_angle(a, b, f):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * f


def bilhar_ease(f):
    f = max(0.0, min(1.0, f))
    return f * f * (3 - 2 * f)


def bilhar_gui(ai_vs_ai=False, level="dificil", fullscreen=True, cpus=None, quem_comeca=0):
    import pygame
    pygame.init()
    OX, OY = 70, 40
    W, H = 1240, 720
    flags = (pygame.FULLSCREEN | pygame.SCALED) if fullscreen else (pygame.SCALED | pygame.RESIZABLE)
    try:
        screen = pygame.display.set_mode((W, H), flags)      # SCALED: ajusta à resolução do ecrã
    except pygame.error:
        screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Bilhar 8 Ball - IA por reforço")
    clock = pygame.time.Clock()
    f_big = pygame.font.SysFont("arial", 30, bold=True)
    f_mid = pygame.font.SysFont("arial", 20, bold=True)
    f_sm = pygame.font.SysFont("arial", 14, bold=True)
    f_num = pygame.font.SysFont("arial", 11, bold=True)
    rng = np.random.default_rng()
    policy = bilhar_Policy.load()
    if policy.fresh:
        print("Sem pesos treinados: a fazer pré-treino inicial da rede profunda...")
        bilhar_pretrain(policy, rng, verbose=False)
        policy.save()

    # simulador paralelo da IA (arranca em segundo plano; entretanto usa 1 processo)
    ev_box = {"ev": None}

    def _mk_ev():
        n = os.cpu_count() or 1
        w = cpus if cpus is not None else (min(n - 1, 6) if n > 2 else 0)
        ev_box["ev"] = bilhar_Evaluator(w)
    threading.Thread(target=_mk_ev, daemon=True).start()

    def make_sprite(b):
        size = 2 * bilhar_R + 2
        c = (bilhar_R + 1, bilhar_R + 1)
        flat = pygame.Surface((size, size), pygame.SRCALPHA)
        white = (246, 246, 240)
        base = white if b == 0 else bilhar_COLORS[b if b < 9 else b - 8]
        pygame.draw.circle(flat, white if (b == 0 or b >= 9) else base, c, bilhar_R)
        if b >= 9:
            for dy in range(-int(bilhar_R * 0.55), int(bilhar_R * 0.55) + 1):
                hw = int(math.sqrt(max(bilhar_R * bilhar_R - dy * dy, 0)))
                pygame.draw.line(flat, base, (c[0] - hw, c[1] + dy), (c[0] + hw, c[1] + dy))
        if b > 0:
            pygame.draw.circle(flat, white, c, bilhar_R // 2 + 1)
            t = f_num.render(str(b), True, (10, 10, 10))
            flat.blit(t, t.get_rect(center=c))
        out = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            for x in range(size):
                dx, dy = (x - c[0]) / bilhar_R, (y - c[1]) / bilhar_R
                r2 = dx * dx + dy * dy
                if r2 > 1.0:
                    continue
                nz = math.sqrt(1 - r2)
                diff = max(0.0, -0.35 * dx - 0.45 * dy + 0.82 * nz)
                light = 0.42 + 0.78 * diff
                spec = (diff ** 22) * 0.6
                col = flat.get_at((x, y))
                alpha = 255 if r2 < 0.88 else int(255 * max(0.0, (1 - r2) / 0.12))
                out.set_at((x, y), (min(255, int(col.r * light + 255 * spec)),
                                    min(255, int(col.g * light + 255 * spec)),
                                    min(255, int(col.b * light + 255 * spec)), alpha))
        return out

    sprites = [make_sprite(b) for b in range(16)]
    minis = [pygame.transform.smoothscale(s, (20, 20)) for s in sprites]
    shadow = pygame.Surface((2 * bilhar_R + 6, 2 * bilhar_R + 6), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 80), (bilhar_R + 3, bilhar_R + 3), bilhar_R)

    def make_table():
        s = pygame.Surface((1100, 620))
        s.fill((24, 24, 30))
        frame = pygame.Rect(bilhar_L - 44, bilhar_T - 44, bilhar_RT - bilhar_L + 88, bilhar_B - bilhar_T + 88)
        pygame.draw.rect(s, (60, 32, 14), frame, border_radius=22)
        pygame.draw.rect(s, (118, 68, 32), frame.inflate(-6, -6), border_radius=20)
        pygame.draw.rect(s, (92, 52, 24), frame.inflate(-30, -30), border_radius=12)
        pygame.draw.rect(s, (12, 74, 42), pygame.Rect(bilhar_L - 15, bilhar_T - 15, bilhar_RT - bilhar_L + 30, bilhar_B - bilhar_T + 30), border_radius=6)
        w, h = bilhar_RT - bilhar_L, bilhar_B - bilhar_T
        xs, ys = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h), indexing="ij")
        k = 1.0 - 0.28 * (xs ** 2 * 0.7 + ys ** 2)
        arr = np.stack([22 * k, 128 * k, 74 * k], axis=-1).clip(0, 255).astype(np.uint8)
        s.blit(pygame.surfarray.make_surface(arr), (bilhar_L, bilhar_T))
        for fx in [bilhar_L + (bilhar_MID - bilhar_L) * q / 4 for q in (1, 2, 3)] + [bilhar_MID + (bilhar_RT - bilhar_MID) * q / 4 for q in (1, 2, 3)]:
            for yy in (bilhar_T - 29, bilhar_B + 29):
                pygame.draw.polygon(s, (230, 215, 170), [(fx, yy - 4), (fx + 4, yy), (fx, yy + 4), (fx - 4, yy)])
        for fy in [bilhar_T + (bilhar_B - bilhar_T) * q / 4 for q in (1, 2, 3)]:
            for xx in (bilhar_L - 29, bilhar_RT + 29):
                pygame.draw.polygon(s, (230, 215, 170), [(xx, fy - 4), (xx + 4, fy), (xx, fy + 4), (xx - 4, fy)])
        pygame.draw.line(s, (60, 160, 100), (bilhar_HEAD[0], bilhar_T), (bilhar_HEAD[0], bilhar_B), 1)
        pygame.draw.circle(s, (60, 160, 100), (int(bilhar_HEAD[0]), int(bilhar_CY)), 3)
        pygame.draw.circle(s, (60, 160, 100), (int(bilhar_RACK[0]), int(bilhar_CY)), 3)
        for kk, (px, py) in enumerate(bilhar_POCKETS):
            pygame.draw.circle(s, (170, 140, 60), (int(px), int(py)), int(bilhar_PR[kk]) + 5)
            pygame.draw.circle(s, (8, 8, 8), (int(px), int(py)), int(bilhar_PR[kk]))
        return s

    table_surf = make_table()
    world = pygame.Surface((1100, 620))
    game = bilhar_Game(rng)
    game.turn = quem_comeca
    # Na abertura, o jogador humano escolhe livremente a posição da branca
    # dentro da cozinha (atrás da linha de saída), antes da primeira tacada.
    if not ai_vs_ai and quem_comeca == 0:
        game.ball_in_hand = True
        game.kitchen = True
    rede_nx = bilhar_rede_athena()
    if rede_nx is not None:
        rede_nx.athena_nova_partida("bilhar")
    names = ["IA 1", "IA 2"] if ai_vs_ai else ["Tu", "IA"]
    is_human = (lambda: False) if ai_vs_ai else (lambda: game.turn == 0)
    st = {"moving": False,
          "msg": ("Escolhe onde colocar a bola branca atrás da linha e clica para confirmar"
                  if (not ai_vs_ai and quem_comeca == 0) else
                  "A ATHENA faz a abertura" if quem_comeca != 0 else
                  "Abertura automática"),
          "aim": 0.0, "power": 0.0, "spin": [0.0, 0.0], "called": None,
          "drag_aim": False, "drag_pow": False, "ai_wait": 0, "ai_box": None, "level": level,
          "timer": 1800, "anims": [], "npk": 0, "anim": None, "hint": None, "vis": 0.0,
          "vis_pull": 12.0, "tick": 0, "flash": 0, "think_base": 0.0}
    SL = pygame.Rect(22, 150, 28, 300)
    SPC, SPR = (86, 560), 34

    def need_call():
        return not game.over and game.targets(game.turn) == [8] and game.groups[game.turn] is not None

    def set_aim(mw):
        a = mw - game.P[0]
        if np.linalg.norm(a) > 3:
            st["aim"] = math.atan2(a[1], a[0])

    def ray(pos, ang):
        d = np.array([math.cos(ang), math.sin(ang)])
        best, hit = 1e9, None
        for ax, lo, hi in ((0, bilhar_L + bilhar_R, bilhar_RT - bilhar_R), (1, bilhar_T + bilhar_R, bilhar_B - bilhar_R)):
            if abs(d[ax]) > 1e-9:
                for lim in (lo, hi):
                    t = (lim - pos[ax]) / d[ax]
                    if 0 < t < best:
                        best = t
        for i in range(1, 16):
            if game.on[i]:
                c = game.P[i] - pos
                tca = c @ d
                if tca <= 0:
                    continue
                d2 = c @ c - tca * tca
                if d2 < (2 * bilhar_R) ** 2:
                    t = tca - math.sqrt((2 * bilhar_R) ** 2 - d2)
                    if 0 < t < best:
                        best, hit = t, i
        return pos + d * best, hit

    def fire_shot(a):
        st["aim"] = a["ang"]
        game.start_shot(a["ang"], a["pw"], a["sp"], a["called"])
        bilhar_registar_tacada(game, a)
        st["moving"], st["npk"] = True, 0
        a["phase"], a["t"] = "follow", 0

    def fire_human():
        if need_call() and st["called"] is None:
            st["msg"] = "Escolhe primeiro a caçapa da bola 8 (clica nela)"
            st["power"] = 0.0
            return
        pw = max(st["power"], 0.04)
        st["anim"] = {"who": "human", "phase": "strike", "t": 0, "ang": st["aim"], "pw": pw,
                      "sp": tuple(st["spin"]), "called": st["called"] if need_call() else None,
                      "pull_start": pw * 55}
        st["vis"], st["vis_pull"] = st["aim"], pw * 55
        st["power"], st["called"] = 0.0, None

    def start_ai():
        g = game.clone()
        box = {"res": None}
        lvl, pl = st["level"], game.turn
        r2 = np.random.default_rng(int(rng.integers(1 << 30)))
        ev = ev_box["ev"] or bilhar_SERIAL
        st["hint"] = None
        tg = game.targets(pl)
        if game.shots == 0:
            tgt = bilhar_RACK
        elif tg:
            tgt = min((game.P[t] for t in tg), key=lambda p: float(np.linalg.norm(p - game.P[0])))
        else:
            tgt = bilhar_RACK
        a0 = tgt - game.P[0]
        st["think_base"] = math.atan2(a0[1], a0[0])
        st["vis"] = st["think_base"] + 0.5

        def hint(a):
            if a is not None:
                st["hint"] = a

        def work():
            try:
                box["res"] = bilhar_ai_think(g, pl, policy, lvl, r2, ev, hint)
            except Exception as ex:                       # a IA nunca deve encravar o jogo
                print("Erro na IA (a usar jogada simples):", repr(ex))
                g2 = game.clone()
                place = None
                if g2.ball_in_hand:
                    bilhar_ai_place(g2, pl, policy, r2)
                    place = g2.P[0].copy()
                    g2.ball_in_hand = False
                ang, pw, sp, called, _ = bilhar_ai_pick(g2, pl, policy, r2)
                box["res"] = (place, ang, pw, sp, called, "direta")
        threading.Thread(target=work, daemon=True).start()
        st["ai_box"], st["ai_wait"] = box, 0

    def advance_anim():
        a = st["anim"]
        if a is None:
            return
        a["t"] += 1
        ph, t = a["phase"], a["t"]
        if a["who"] == "ai":
            if ph == "aim":
                f = bilhar_ease(t / 28.0)
                st["vis"] = bilhar_lerp_angle(a["vis0"], a["ang"], f)
                st["vis_pull"] = a["pull0"] + (10.0 - a["pull0"]) * f
                if t >= 28:
                    a["phase"], a["t"] = "pull", 0
            elif ph == "pull":
                f = bilhar_ease(t / 26.0)
                st["vis"] = a["ang"]
                st["vis_pull"] = 10.0 + (a["pw"] * 62.0) * f
                if t >= 26:
                    a["phase"], a["t"] = "hold", 0
            elif ph == "hold":
                st["vis_pull"] = 10.0 + a["pw"] * 62.0 + 1.2 * math.sin(t * 1.3)
                if t >= 12:
                    a["phase"], a["t"], a["pull_start"] = "strike", 0, st["vis_pull"]
        if a["phase"] == "strike":
            f = min(1.0, a["t"] / 6.0)
            st["vis_pull"] = a["pull_start"] * (1 - f * f)
            if a["t"] >= 6:
                fire_shot(a)
        elif a["phase"] == "follow":
            st["vis_pull"] = -5.0 * min(1.0, a["t"] / 3.0)
            if a["t"] >= 12:
                st["anim"] = None

    def draw_ball(i):
        x, y = int(game.P[i][0]), int(game.P[i][1])
        world.blit(shadow, (x - bilhar_R - 3 + 3, y - bilhar_R - 3 + 4))
        world.blit(sprites[i], (x - bilhar_R - 1, y - bilhar_R - 1))

    CUE_PARTS = [(0, 3, 2.4, 2.6, (88, 150, 220)), (3, 13, 2.6, 2.9, (242, 242, 236)),
                 (13, 172, 2.9, 4.3, (232, 196, 138)), (172, 178, 4.3, 4.5, (38, 28, 22)),
                 (178, 288, 4.5, 6.3, (96, 54, 30)), (288, 296, 6.3, 6.5, (28, 20, 16))]

    def draw_cue(pos, ang, pull):
        d = np.array([math.cos(ang), math.sin(ang)])
        n = np.array([-d[1], d[0]])
        s = np.asarray(pos, float) + (OX, OY) - d * (bilhar_R + 3 + pull)
        for a0, a1, w0, w1, col in CUE_PARTS:
            p0, p1 = s - d * a0, s - d * a1
            pygame.draw.polygon(screen, col, [tuple(p0 + n * w0), tuple(p0 - n * w0),
                                              tuple(p1 - n * w1), tuple(p1 + n * w1)])
        for sg in (1, -1):
            pygame.draw.line(screen, (40, 26, 16), tuple(s - d * 13 + n * 2.9 * sg), tuple(s - d * 296 + n * 6.5 * sg), 1)
        pygame.draw.line(screen, (255, 244, 214), tuple(s - d * 14 + n * 1.0), tuple(s - d * 170 + n * 1.6), 1)
        for off in (196, 214, 232):
            c0 = s - d * off
            w = 4.5 + (off - 178) / 110 * 1.8
            pygame.draw.line(screen, (196, 154, 92), tuple(c0 + n * w), tuple(c0 - n * w), 2)

    def player_card(p, x, align_right=False):
        active = (game.turn == p) and not game.over
        rect = pygame.Rect(x, 8, 470, 66)
        pygame.draw.rect(screen, (46, 46, 58) if not active else (60, 80, 70), rect, border_radius=10)
        if active:
            pygame.draw.rect(screen, (250, 210, 90), rect, 2, border_radius=10)
            if not st["moving"]:
                fr_ = max(0.0, st["timer"] / 1800.0) if is_human() else 1.0
                pygame.draw.rect(screen, (int(240 - 180 * fr_), int(70 + 150 * fr_), 70),
                                 (x + 6, 70, int(458 * fr_), 4), border_radius=2)
        screen.blit(f_mid.render(names[p], True, (240, 240, 240)), (x + 12, 12))
        g = game.groups[p]
        label = {None: "mesa aberta", "solid": "lisas", "stripe": "listradas"}[g]
        screen.blit(f_sm.render(label, True, (190, 190, 200)), (x + 12, 40))
        if g:
            ids = bilhar_ids_of(g) if any(game.on[b] for b in bilhar_ids_of(g)) else [8]
            for n_, b in enumerate(ids):
                im = minis[b]
                if not game.on[b]:
                    im = im.copy()
                    im.set_alpha(70)
                screen.blit(im, (x + 110 + n_ * 24, 22))

    def update_msg(res, who):
        st["msg"] = f"{names[who]}: {res['msg']}"

    try:
        while True:
            st["tick"] += 1
            mouse = np.array(pygame.mouse.get_pos(), float)
            mw = mouse - (OX, OY)
            can_act = is_human() and not st["moving"] and not game.over and st["anim"] is None
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return "menu"
                if game.over and ((ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE)) or
                                  (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1)):
                    return "win" if game.winner == 0 else "loss"
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                    elif ev.key == pygame.K_r:
                        game.reset()
                        game.turn = quem_comeca
                        if not ai_vs_ai and quem_comeca == 0:
                            game.ball_in_hand = True
                            game.kitchen = True
                        if rede_nx is not None:
                            rede_nx.athena_nova_partida("bilhar")
                        st.update(moving=False, ai_box=None, called=None, power=0.0, timer=1800, anims=[], npk=0,
                                  msg=("Escolhe onde colocar a bola branca atrás da linha e clica para confirmar"
                                       if not ai_vs_ai and quem_comeca == 0 else "Novo jogo"),
                                  spin=[0.0, 0.0], anim=None, hint=None, flash=0)
                    elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        st["level"] = bilhar_LEVEL_KEYS[ev.key - pygame.K_1]
                        st["msg"] = f"Nível da IA: {st['level']}"
                if not can_act:
                    continue
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    pos = np.array(ev.pos, float)
                    if SL.inflate(14, 14).collidepoint(ev.pos) and not game.ball_in_hand:
                        st["drag_pow"] = True
                        st["power"] = float(np.clip((pos[1] - SL.top) / SL.height, 0, 1))
                    elif np.linalg.norm(pos - SPC) <= SPR:
                        v = (pos - SPC) / SPR
                        st["spin"] = [float(v[0]), float(-v[1])]
                    elif game.ball_in_hand:
                        if game.valid_spot(pos - (OX, OY)):
                            game.P[0] = pos - (OX, OY)
                            game.ball_in_hand = False
                            st["msg"] = "Bola colocada - aponta e tacar"
                    else:
                        w = pos - (OX, OY)
                        if need_call():
                            near = np.linalg.norm(bilhar_POCKETS - w, axis=1)
                            if near.min() < 40:
                                st["called"] = int(near.argmin())
                                continue
                        st["drag_aim"] = True
                        set_aim(w)
                elif ev.type == pygame.MOUSEMOTION:
                    if st["drag_aim"]:
                        set_aim(mw)
                    if st["drag_pow"]:
                        st["power"] = float(np.clip((ev.pos[1] - SL.top) / SL.height, 0, 1))
                elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    st["drag_aim"] = False
                    if st["drag_pow"]:
                        st["drag_pow"] = False
                        if st["power"] > 0.04:
                            fire_human()
                        else:
                            st["power"] = 0.0
            keys = pygame.key.get_pressed()
            if can_act and not game.ball_in_hand:
                fine = 0.0006 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else 0.004
                if keys[pygame.K_LEFT]:
                    st["aim"] -= fine
                if keys[pygame.K_RIGHT]:
                    st["aim"] += fine

            # tempo de jogada (30 s): se esgotar é falta
            if can_act:
                st["timer"] -= 1
                if st["timer"] <= 0:
                    who = game.turn
                    game.turn, game.ball_in_hand, game.kitchen = 1 - who, True, False
                    st.update(timer=1800, power=0.0, drag_aim=False, drag_pow=False,
                              msg=f"{names[who]}: tempo esgotado - falta, bola na mão")

            # IA: pensa numa thread, o taco acompanha a melhor tacada encontrada, depois aponta, puxa e bate
            if not game.over and not st["moving"] and not is_human() and st["anim"] is None:
                if st["ai_box"] is None:
                    start_ai()
                else:
                    st["ai_wait"] += 1
                    tgt = st["hint"] if st["hint"] is not None else st["think_base"] + 0.28 * math.sin(st["tick"] * 0.035)
                    st["vis"] = bilhar_lerp_angle(st["vis"], tgt, 0.07)
                    st["vis_pull"] = 12.0 + 5.0 * math.sin(st["tick"] * 0.12)
                    if st["ai_box"]["res"] is not None and st["ai_wait"] > 30:
                        place, ang, pw, sp, called, kind = st["ai_box"]["res"]
                        st["ai_box"] = None
                        a = {"who": "ai", "phase": "aim", "t": 0, "ang": ang, "pw": pw, "sp": sp, "called": called,
                             "vis0": st["vis"], "pull0": st["vis_pull"]}
                        if place is not None:
                            game.P[0] = place
                            game.V[0] = 0
                            game.ball_in_hand = False
                            st["flash"] = 40
                            a["vis0"] = ang
                        st["anim"] = a
                        st["msg"] = f"{names[game.turn]}: {bilhar_KIND_TXT.get(kind, kind)}"
            advance_anim()
            if not st["moving"] and st["anim"] is not None and st["anim"]["phase"] == "follow":
                st["anim"] = None

            if st["moving"]:
                for _ in range(2):
                    running = game.step()
                    if len(game.pocketed) > st["npk"]:
                        for b in game.pocketed[st["npk"]:]:
                            st["anims"].append([b, game.P[b].copy(), game.pocket_of[b], 0])
                        st["npk"] = len(game.pocketed)
                    if not running:
                        st["moving"], st["timer"] = False, 1800
                        who = game.turn
                        update_msg(game.end_shot(), who)
                        break

            screen.fill((28, 28, 36))
            world.blit(table_surf, (0, 0))
            if need_call() and not st["moving"]:
                for k in range(6):
                    pygame.draw.circle(world, (250, 210, 90) if st["called"] == k else (255, 255, 255),
                                       bilhar_POCKETS[k].astype(int), int(bilhar_PR[k]) + 7, 3 if st["called"] == k else 1)
            if game.kitchen and game.ball_in_hand:
                cozinha = pygame.Rect(bilhar_L, bilhar_T, int(bilhar_HEAD[0]) - bilhar_L, bilhar_B - bilhar_T)
                pygame.draw.rect(world, (255, 255, 255), cozinha, 2)
                aviso = f_sm.render("COLOCA A BRANCA AQUI", True, (255, 245, 190))
                world.blit(aviso, (cozinha.centerx - aviso.get_width() // 2, cozinha.top + 12))
            for i in range(16):
                if game.on[i]:
                    draw_ball(i)
            for a in list(st["anims"]):
                f = a[3] / 14.0
                pos = a[1] + (bilhar_POCKETS[a[2]] - a[1]) * f
                sz = max(4, int((2 * bilhar_R + 2) * (1 - 0.75 * f)))
                world.blit(pygame.transform.smoothscale(sprites[a[0]], (sz, sz)), (int(pos[0] - sz / 2), int(pos[1] - sz / 2)))
                a[3] += 1
                if a[3] > 14:
                    st["anims"].remove(a)
            if st["flash"] > 0 and game.on[0]:
                st["flash"] -= 1
                pygame.draw.circle(world, (255, 255, 255), game.P[0].astype(int), bilhar_R + 3 + (st["flash"] % 20) // 4, 2)

            cue_draw = None                          # (ângulo, recuo) do taco a desenhar por cima da mesa
            anim = st["anim"]
            if can_act:
                if game.ball_in_hand:
                    ok = game.valid_spot(mw)
                    pygame.draw.circle(world, (250, 250, 245) if ok else (210, 60, 60), mw.astype(int), bilhar_R, 2)
                else:
                    cue = game.P[0]
                    ang = st["aim"]
                    end, hit = ray(cue, ang)
                    pygame.draw.line(world, (255, 255, 255), cue.astype(int), end.astype(int), 2)
                    pygame.draw.circle(world, (255, 255, 255), end.astype(int), bilhar_R, 2)
                    d = np.array([math.cos(ang), math.sin(ang)])
                    if hit is not None:
                        nrm = game.P[hit] - end
                        nrm /= np.linalg.norm(nrm)
                        tg = d - (d @ nrm) * nrm
                        if np.linalg.norm(tg) > 0.05:
                            pygame.draw.line(world, (200, 200, 200), end.astype(int), (end + tg * 45).astype(int), 1)
                    cue_draw = (ang, st["power"] * 55 if st["drag_pow"] else 0.0)
            elif anim is not None and not game.over:
                if anim["who"] == "ai" and anim["phase"] in ("pull", "hold", "strike") or \
                        (anim["who"] == "ai" and anim["phase"] == "aim" and anim["t"] > 10):
                    if anim["called"] is not None:
                        pygame.draw.circle(world, (250, 210, 90), bilhar_POCKETS[anim["called"]].astype(int),
                                           int(bilhar_PR[anim["called"]]) + 7, 3)
                cue_draw = (st["vis"], st["vis_pull"])
            elif not game.over and not st["moving"] and not is_human() and st["ai_box"] is not None \
                    and not game.ball_in_hand:
                cue_draw = (st["vis"], st["vis_pull"])  # a IA está a pensar: o taco anda à volta da branca
            screen.blit(world, (OX, OY))
            if cue_draw is not None and game.on[0]:
                draw_cue(game.P[0], cue_draw[0], cue_draw[1])

            # barra de força e efeito
            pygame.draw.rect(screen, (50, 50, 60), SL, border_radius=8)
            fill = int(SL.height * st["power"])
            if fill > 0:
                col = (int(60 + 190 * st["power"]), int(210 - 150 * st["power"]), 70)
                pygame.draw.rect(screen, col, (SL.x, SL.y, SL.w, fill), border_radius=8)
            pygame.draw.circle(screen, (240, 240, 240), (SL.centerx, SL.y + fill), 14)
            screen.blit(f_sm.render("FORÇA", True, (200, 200, 210)), (SL.x - 4, SL.y - 22))
            pygame.draw.circle(screen, (246, 246, 240), SPC, SPR)
            pygame.draw.line(screen, (190, 190, 190), (SPC[0] - SPR, SPC[1]), (SPC[0] + SPR, SPC[1]))
            pygame.draw.line(screen, (190, 190, 190), (SPC[0], SPC[1] - SPR), (SPC[0], SPC[1] + SPR))
            pygame.draw.circle(screen, (210, 30, 30),
                               (int(SPC[0] + st["spin"][0] * SPR * 0.8), int(SPC[1] - st["spin"][1] * SPR * 0.8)), 6)
            screen.blit(f_sm.render("EFEITO", True, (200, 200, 210)), (SPC[0] - 24, SPC[1] + SPR + 6))

            player_card(0, 130)
            player_card(1, 640)
            ev_ = ev_box["ev"]
            par = f" x{ev_.n}" if ev_ is not None and ev_.n > 1 else ""
            screen.blit(f_sm.render(f"IA: {st['level']}{par} (1-4)",
                                    True, (170, 170, 185)), (990, 700))
            thinking = (not game.over) and (not st["moving"]) and (not is_human()) and st["anim"] is None
            txt = st["msg"] + ("  (a IA está a pensar" + "." * (1 + (st["tick"] // 15) % 3) + ")" if thinking else "")
            screen.blit(f_mid.render(txt, True, (255, 232, 130)), (130, 668))
            if game.over:
                t = f_big.render(f"Fim de jogo! Vencedor: {names[game.winner]}  (R reinicia)", True, (255, 255, 255))
                bg = t.get_rect(center=(W // 2, 340)).inflate(40, 24)
                pygame.draw.rect(screen, (20, 20, 28), bg, border_radius=12)
                screen.blit(t, t.get_rect(center=(W // 2, 340)))
            pygame.display.flip()
            clock.tick(60)
    finally:
        if ev_box["ev"] is not None:
            ev_box["ev"].close()





# ========================================================================
# ATHENA_NEXUS — código integrado
# ========================================================================


# -*- coding: utf-8 -*-
"""ATHENA NEXUS: campanha de jogos contra a ATHENA.
Requisitos: Python 3.10+, pygame e numpy (voz, microfone e Ollama são opcionais).
Todos os jogos estão integrados neste único ficheiro."""
import os, sys, base64, json, traceback
import queue as _queue
import random as _random
import threading as _threading
import time as _time
import urllib.request, urllib.error
import socket, subprocess
import numpy as np


nexus_AQUI = os.path.dirname(os.path.abspath(__file__))

# Histórico cronológico da partida atual: {jogo: [(quem, jogada), ...]}. 'quem' é sempre
# 'jogador', 'ATHENA' ou 'parceiro'; cada entrada é uma jogada/tacada realmente executada.
nexus_ATHENA_MOVE_LOG = {}
nexus_ATHENA_ANNOUNCER = None
nexus_ATHENA_MIC = None
nexus_ATHENA_BRAIN = None
nexus_LOG_LOCK = _threading.Lock()


def nexus_eh_jogador(quem):
    return str(quem).strip().lower() == "jogador"


def nexus_athena_record_move(jogo, quem, jogada):
    try:
        entrada = (str(quem), str(jogada))
        with nexus_LOG_LOCK:
            lista = nexus_ATHENA_MOVE_LOG.setdefault(str(jogo), [])
            lista.append(entrada)
            recentes = lista[-8:]
        anunciante = nexus_ATHENA_ANNOUNCER
        if anunciante is not None:
            anunciante.on_move(str(jogo), entrada, recentes)
    except Exception as exc:
        print("[ATHENA registo] Não foi possível registar a jogada:", repr(exc))


def nexus_athena_nova_partida(jogo):
    with nexus_LOG_LOCK:
        nexus_ATHENA_MOVE_LOG[str(jogo)] = []
    if nexus_ATHENA_BRAIN is not None:
        nexus_ATHENA_BRAIN.limpar(str(jogo))
    anunciante = nexus_ATHENA_ANNOUNCER
    if anunciante is not None:
        anunciante.nova_partida(str(jogo))


# NÚCLEO NEURONAL MULTIJOGO — tronco partilhado + uma cabeça por jogo
class nexus_ATHENAMultiGameBrain:
    GAMES = ("quatro", "damas", "bilhar", "xadrez", "sueca")
    SHAPES = (17, 512, 1024, 2048, 1024, 512)
    ESCALA_BASE = {"quatro": 1000.0, "damas": 500.0, "xadrez": 300.0, "bilhar": 10.0,
                   "sueca": 300.0}
    LR_CABECA = 2e-3
    LR_TRONCO = 2e-5

    def __init__(self, path=None, seed=41):
        self.path = path or os.path.join(nexus_AQUI, "athena_rede_multijogo.npz")
        self._lock = _threading.RLock()
        self._save_lock = _threading.Lock()
        self._threads = []
        self.W = [None] * (len(self.SHAPES) - 1)
        self.b = [None] * (len(self.SHAPES) - 1)
        self.heads = {g: np.zeros((512, 1), dtype=np.float32) for g in self.GAMES}
        self.pending = {g: [] for g in self.GAMES}
        self._ativo = {g: False for g in self.GAMES}
        self._load()
        rng = np.random.default_rng(seed)
        for i, (a, z) in enumerate(zip(self.SHAPES[:-1], self.SHAPES[1:])):
            if self.W[i] is None:
                self.W[i] = (rng.standard_normal((a, z)) * np.sqrt(1.0 / a)).astype(np.float32)
            if self.b[i] is None:
                self.b[i] = np.zeros(z, dtype=np.float32)
        self._atualizar_ativos()

    # ---------------------------------------------------------------- ficheiro
    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with np.load(self.path, allow_pickle=False) as d:
                if "version" in d.files and int(d["version"][0]) != 1:
                    return
                for i, (a, z) in enumerate(zip(self.SHAPES[:-1], self.SHAPES[1:])):
                    if f"W{i}" in d.files and d[f"W{i}"].shape == (a, z):
                        self.W[i] = d[f"W{i}"].astype(np.float32)
                    if f"b{i}" in d.files and d[f"b{i}"].shape == (z,):
                        self.b[i] = d[f"b{i}"].astype(np.float32)
                for g in self.GAMES:
                    if f"H_{g}" in d.files and d[f"H_{g}"].shape == (512, 1):
                        self.heads[g] = d[f"H_{g}"].astype(np.float32)
        except Exception as exc:
            print("[ATHENA rede] Pesos multijogo não carregados:", repr(exc))

    def _atualizar_ativos(self):
        for g in self.GAMES:
            self._ativo[g] = bool(np.any(self.heads[g]))

    def save(self):
        with self._save_lock:
            with self._lock:
                payload = {"version": np.array([1], dtype=np.int32)}
                for i, (w, b) in enumerate(zip(self.W, self.b)):
                    payload[f"W{i}"] = w.copy()
                    payload[f"b{i}"] = b.copy()
                for g, h in self.heads.items():
                    payload[f"H_{g}"] = h.copy()
            try:
                comum_escrever_npz(self.path, payload)
            except Exception as exc:
                print("[ATHENA rede] Não foi possível guardar a rede:", repr(exc))

    def esperar(self, timeout=10.0):
        fim = _time.time() + timeout
        for t in list(self._threads):
            t.join(max(0.0, fim - _time.time()))

    # ------------------------------------------------------------ codificação
    @staticmethod
    def _numeros(obj, saida, limite, profundidade=0):
        if len(saida) >= limite or profundidade > 5 or obj is None:
            return
        if isinstance(obj, (bool, np.bool_)):
            saida.append(1.0 if obj else 0.0)
        elif isinstance(obj, (int, np.integer)):
            v = int(obj)
            if abs(v) > (1 << 20):
                saida.append(min(1.0, bin(abs(v)).count("1") / 64.0))
            elif abs(v) <= 64:
                saida.append(v / 64.0)
            else:
                saida.append(float(np.tanh(v / 1000.0)))
        elif isinstance(obj, (float, np.floating)):
            v = float(obj)
            if v != v or v in (float("inf"), float("-inf")):
                saida.append(0.0)
            elif abs(v) <= 4.0:
                saida.append(v / 4.0)
            else:
                saida.append(float(np.tanh(v / 100.0)))
        elif isinstance(obj, str):
            if obj:
                saida.append((sum((i + 1) * ord(c) for i, c in enumerate(obj[:32])) % 997) / 997.0)
        elif isinstance(obj, dict):
            for k, v in list(obj.items())[:20]:
                nexus_ATHENAMultiGameBrain._numeros(k, saida, limite, profundidade + 1)
                nexus_ATHENAMultiGameBrain._numeros(v, saida, limite, profundidade + 1)
        elif isinstance(obj, (list, tuple, np.ndarray)):
            seq = obj.reshape(-1).tolist() if isinstance(obj, np.ndarray) else list(obj)
            for v in seq[:64]:
                nexus_ATHENAMultiGameBrain._numeros(v, saida, limite, profundidade + 1)

    def encode(self, game, state, action, base=0.0):
        escala = self.ESCALA_BASE.get(game, 100.0)
        x = np.zeros(17, dtype=np.float32)
        x[0] = np.float32(np.tanh(float(base) / escala))
        x[1] = np.float32((self.GAMES.index(game) + 1) / 7.0)
        a, s = [], []
        self._numeros(action, a, 8)
        self._numeros(state, s, 7)
        for i, v in enumerate(a[:8]):
            x[2 + i] = np.float32(np.clip(v, -1.0, 1.0))
        for i, v in enumerate(s[:7]):
            x[10 + i] = np.float32(np.clip(v, -1.0, 1.0))
        return x

    # ---------------------------------------------------------------- inferência
    def ativo(self, game):
        return self._ativo.get(game, False)

    def forward(self, game, X):
        with self._lock:
            H = X
            caches = [X]
            for W, b in zip(self.W, self.b):
                H = np.tanh(H @ W + b).astype(np.float32)
                caches.append(H)
            return (H @ self.heads[game]).reshape(-1), caches

    def vies(self, game, candidatos, estado=None):
        if len(candidatos) < 2 or not self.ativo(game):
            return None
        feats = np.stack([self.encode(game, estado, c, 0.0) for c in candidatos])
        nn, _ = self.forward(game, feats)
        return np.tanh(nn).tolist()

    def registar_escolha(self, game, candidato, estado=None, base=0.0):
        with self._lock:
            amostras = self.pending[game]
            amostras.append(self.encode(game, estado, candidato, base))
            if len(amostras) > 96:
                del amostras[:-96]

    def rank(self, game, candidates, state, record=True):
        if not candidates:
            return candidates
        base = np.array([float(s) for s, _ in candidates], dtype=np.float64)
        amplitude = float(base.max() - base.min())
        norm = (base - base.max()) / (amplitude if amplitude > 1e-9 else 1.0)
        total = norm
        if len(candidates) > 1 and self.ativo(game):
            feats = np.stack([self.encode(game, state, a, s) for s, a in candidates])
            nn, _ = self.forward(game, feats)
            total = norm + 0.15 * np.tanh(nn)
        ordem = np.argsort(-total, kind="stable")
        if record:
            s0, a0 = candidates[int(ordem[0])]
            self.registar_escolha(game, a0, state, s0)
        return [candidates[int(i)] for i in ordem]

    def choose(self, game, candidates, state, base_scores=None, record=True):
        if not candidates:
            return None
        scores = base_scores if base_scores is not None else [0.0] * len(candidates)
        return self.rank(game, list(zip(scores, candidates)), state, record=record)[0][1]

    def record(self, game, state, action, base=0.0):
        self.registar_escolha(game, action, state, base)

    def limpar(self, game):
        with self._lock:
            if game in self.pending:
                self.pending[game].clear()

    # ------------------------------------------------------------------ treino
    def finish(self, game, reward):
        with self._lock:
            amostras = [x.copy() for x in self.pending.get(game, [])[-24:]]
            self.pending[game] = []
        if not amostras or abs(float(reward)) < 1e-9:
            return

        def trabalho():
            try:
                self._treinar(game, amostras, float(np.clip(reward, -1, 1)))
                self.save()
            except Exception as exc:
                print("[ATHENA rede] Atualização adiada:", repr(exc))
        t = _threading.Thread(target=trabalho, daemon=True, name="ATHENA-Treino")
        self._threads = [x for x in self._threads if x.is_alive()] + [t]
        t.start()

    def _treinar(self, game, amostras, alvo):
        # O alvo é o resultado da PARTIDA para a ATHENA: a vitória do jogador é mau para ela.
        alvo = -alvo
        with self._lock:
            n = len(amostras)
            for x in amostras:
                X = x[None, :]
                pred, caches = self.forward(game, X)
                erro = float(np.clip(pred[0] - alvo, -2.0, 2.0))
                grad = np.full((1, 1), 2.0 * erro / n, dtype=np.float32)
                h = caches[-1]
                dh = grad @ self.heads[game].T                    # antes de alterar a cabeça
                self.heads[game] = np.clip(self.heads[game] - self.LR_CABECA * (h.T @ grad), -5.0, 5.0)
                for i in range(len(self.W) - 1, -1, -1):
                    a = caches[i + 1]
                    dz = dh * (1 - a * a)
                    gW = caches[i].T @ dz
                    dh = dz @ self.W[i].T                         # antes de alterar W[i]
                    self.W[i] -= self.LR_TRONCO * np.clip(gW, -1, 1)
                    self.b[i] -= self.LR_TRONCO * np.clip(dz.sum(axis=0), -1, 1)
            self._atualizar_ativos()


def nexus_cerebro():
    global nexus_ATHENA_BRAIN
    if nexus_ATHENA_BRAIN is None:
        nexus_ATHENA_BRAIN = nexus_ATHENAMultiGameBrain()
    return nexus_ATHENA_BRAIN


# Pontes usadas pelo módulo de bilhar (mantêm a API que o jogo espera).
athena_record_move = nexus_athena_record_move
athena_nova_partida = nexus_athena_nova_partida
athena_ativo = lambda jogo: nexus_cerebro().ativo(jogo)
athena_vies = lambda jogo, candidatos, estado=None: nexus_cerebro().vies(jogo, candidatos, estado)
athena_escolha = lambda jogo, candidato, estado=None: nexus_cerebro().registar_escolha(jogo, candidato, estado)


def nexus_instalar_ganchos():
    global comum_athena_brain, comum_athena_record_move, comum_athena_nova_partida
    global comum_athena_ativo, comum_athena_vies, comum_athena_escolha
    cerebro = nexus_cerebro()
    comum_athena_brain = cerebro
    comum_athena_record_move = nexus_athena_record_move
    comum_athena_nova_partida = nexus_athena_nova_partida
    comum_athena_ativo = cerebro.ativo
    comum_athena_vies = cerebro.vies
    comum_athena_escolha = lambda jogo, candidato, estado=None: cerebro.registar_escolha(jogo, candidato, estado)


# Utilitários de interface partilhados pelos jogos de cartas e tabuleiro
def nexus_alternar_ecra(pygame):
    try:
        pygame.display.toggle_fullscreen()
    except pygame.error:
        pass


def nexus_centro_x():
    return comum_W // 2


# SUECA — quatro jogadores (tu + parceiro contra a ATHENA), 40 cartas, 120 pontos
nexus_NAIPES = ["Paus", "Ouros", "Espadas", "Copas"]
nexus_SIMBOLOS = ["♣", "♦", "♠", "♥"]
nexus_VALORES = ["2", "3", "4", "5", "6", "Q", "J", "K", "7", "A"]          # da mais fraca à mais forte
nexus_PONTOS = {"A": 11, "7": 10, "K": 4, "J": 3, "Q": 2, "6": 0, "5": 0, "4": 0, "3": 0, "2": 0}
nexus_ORDEM = {v: i for i, v in enumerate(nexus_VALORES)}


def nexus_baralho():
    return [(n, v) for n in range(4) for v in nexus_VALORES]


def nexus_pontos(c):
    return nexus_PONTOS[c[1]]


def nexus_vencedor(vaza, trunfo):
    naipe_saida = vaza[0][1][0]

    def chave(item):
        _, (naipe, valor) = item
        grupo = 2 if naipe == trunfo else 1 if naipe == naipe_saida else 0
        return (grupo, nexus_ORDEM[valor])
    return max(vaza, key=chave)[0]


def nexus_legal(mao, naipe_saida):
    do_naipe = [c for c in mao if c[0] == naipe_saida]
    return do_naipe if do_naipe else list(mao)


def nexus_escolha_ia(mao, vaza, trunfo, parceiro, equipa, registar=True):
    cerebro = nexus_cerebro()
    estado = (mao, vaza, trunfo, parceiro, equipa)
    legais = nexus_legal(mao, vaza[0][1][0]) if vaza else list(mao)
    if not vaza:
        bases = [-float(nexus_pontos(c) * 100 + nexus_ORDEM[c[1]]) for c in legais]
        return cerebro.choose("sueca", legais, estado, bases, record=registar)
    lider = nexus_vencedor(vaza, trunfo)
    parceiro_ganha = lider in equipa

    def custo(c):
        ganha = nexus_vencedor(vaza + [(-1, c)], trunfo) == -1
        if parceiro_ganha:
            return (0 if not ganha else 3, nexus_pontos(c), nexus_ORDEM[c[1]])
        return (0 if ganha else 2, nexus_pontos(c) if ganha else -nexus_pontos(c), nexus_ORDEM[c[1]])
    bases = [-float(sum(custo(c))) for c in legais]
    return cerebro.choose("sueca", legais, estado, bases, record=registar)


def nexus_desenhar_carta(pygame, screen, rect, carta, borda=(110, 110, 110), mostrar_pontos=True):
    pygame.draw.rect(screen, (236, 232, 215), rect, border_radius=8)
    pygame.draw.rect(screen, borda, rect, 3, border_radius=8)
    cor = (190, 45, 55) if carta[0] in (1, 3) else (25, 30, 38)
    comum_texto(screen, f"{nexus_SIMBOLOS[carta[0]]} {carta[1]}", rect.center, 22, cor, "center")
    if mostrar_pontos:
        comum_texto(screen, f"{nexus_PONTOS[carta[1]]} pts", (rect.centerx, rect.bottom - 16), 12, (60, 60, 60), "center", False)


def nexus_sueca_jogar(screen, clock, nivel="normal", quem_comeca=0):
    import pygame
    rng = _random.Random()
    erro_athena, erro_parceiro = {"facil": (0.48, 0.30), "normal": (0.28, 0.12),
                                  "dificil": (0.12, 0.06), "mestre": (0.0, 0.0)}.get(nivel, (0.28, 0.12))
    baralho = nexus_baralho()
    rng.shuffle(baralho)
    maos = [baralho[i * 10:(i + 1) * 10] for i in range(4)]
    trunfo_carta = baralho[-1]               # a última carta distribuída define o trunfo
    trunfo = trunfo_carta[0]
    maos[0].sort(key=lambda c: (c[0], nexus_ORDEM[c[1]]))
    pontos = [0, 0]
    jogador = 0 if quem_comeca == 0 else 1   # lugar que joga: 0 = tu, 1 = ATHENA, 2 = parceiro, 3 = ATHENA
    vaza = []
    vaza_vista = []
    fase = "jogar"                           # jogar | pausa | fim
    vencedor_vaza = None
    pronto_em = pygame.time.get_ticks() + 400
    fim_pausa = 0
    msg = "A tua equipa és tu + o parceiro (em frente). A ATHENA joga com Este e Oeste."
    nomes = ["TU", "ATHENA — ESTE", "PARCEIRO", "ATHENA — OESTE"]
    posicoes_nome = [(620, 505), (1085, 285), (620, 150), (155, 285)]
    posicoes_vaza = [(620, 368), (735, 300), (620, 232), (505, 300)]
    nexus_athena_nova_partida("sueca")

    def veredito():
        return "win" if pontos[0] > 60 else "loss" if pontos[1] > 60 else "draw"

    def jogar_carta(lugar, carta):
        nonlocal jogador, fase, fim_pausa, vencedor_vaza, vaza_vista, msg, pronto_em
        agora = pygame.time.get_ticks()
        maos[lugar].remove(carta)
        vaza.append((lugar, carta))
        quem = "jogador" if lugar == 0 else "parceiro" if lugar == 2 else "ATHENA"
        nexus_athena_record_move("sueca", quem, f"{nexus_NAIPES[carta[0]]} {carta[1]}")
        if len(vaza) < 4:
            jogador = (lugar + 1) % 4
            pronto_em = agora + 650
            return
        ganhador = nexus_vencedor(vaza, trunfo)
        ganho = sum(nexus_pontos(c) for _, c in vaza)
        pontos[0 if ganhador % 2 == 0 else 1] += ganho
        vaza_vista = list(vaza)
        vencedor_vaza = ganhador
        fase = "pausa"
        fim_pausa = agora + 1500
        msg = f"Vaza para {'a tua equipa' if ganhador % 2 == 0 else 'a ATHENA'} (+{ganho} pontos)"

    def retomar():
        nonlocal fase, jogador, vaza, vaza_vista, pronto_em
        jogador = vencedor_vaza
        vaza = []
        vaza_vista = []
        if not any(maos):
            fase = "fim"
        else:
            fase = "jogar"
            pronto_em = pygame.time.get_ticks() + 450

    def rects_mao():
        n = len(maos[0])
        passo = 100
        total = (n - 1) * passo + 88 if n else 0
        x0 = (comum_W - total) // 2
        return [pygame.Rect(x0 + i * passo, 548, 88, 130) for i in range(n)]

    while True:
        agora = pygame.time.get_ticks()
        legais = nexus_legal(maos[0], vaza[0][1][0]) if vaza else list(maos[0])
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                elif e.key == pygame.K_ESCAPE:
                    return "menu"
                elif fase == "fim" and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return veredito()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if fase == "fim":
                    return veredito()
                if fase == "jogar" and jogador == 0:
                    for carta, r in zip(maos[0], rects_mao()):
                        if r.collidepoint(e.pos):
                            if carta in legais:
                                jogar_carta(0, carta)
                            else:
                                msg = f"Tens de assistir ao naipe: {nexus_NAIPES[vaza[0][1][0]]}."
                            break
        # Jogadas do computador (com pausa, para se ver o que aconteceu)
        if fase == "jogar" and jogador != 0 and agora >= pronto_em:
            parceiro_do_jogador = (jogador == 2)
            erro = erro_parceiro if parceiro_do_jogador else erro_athena
            opcoes = nexus_legal(maos[jogador], vaza[0][1][0]) if vaza else list(maos[jogador])
            if rng.random() < erro:
                carta = rng.choice(opcoes)
            else:
                equipa = {0, 2} if jogador % 2 == 0 else {1, 3}
                carta = nexus_escolha_ia(maos[jogador], vaza, trunfo, (jogador + 2) % 4, equipa,
                                    registar=not parceiro_do_jogador)
            jogar_carta(jogador, carta)
        if fase == "pausa" and agora >= fim_pausa:
            retomar()
        # ------------------------------------------------------------ desenho
        screen.fill((18, 28, 34))
        cx = nexus_centro_x()
        comum_texto(screen, "ATHENA  /  SUECA", (cx, 30), 30, comum_TXT, "center")
        comum_texto(screen, f"TUA EQUIPA  {pontos[0]}     —     {pontos[1]}  ATHENA", (cx, 74), 24, comum_TXT, "center")
        comum_texto(screen, f"TRUNFO: {nexus_SIMBOLOS[trunfo]} {nexus_NAIPES[trunfo].upper()}   (carta: {nexus_SIMBOLOS[trunfo]}{trunfo_carta[1]})",
                    (cx, 106), 19, comum_OURO, "center")
        for lugar, nome in enumerate(nomes):
            ativo = fase == "jogar" and jogador == lugar
            x, y = posicoes_nome[lugar]
            comum_texto(screen, nome, (x, y), 16, comum_OURO if ativo else comum_DIM, "center")
            if lugar != 0:
                comum_texto(screen, f"{len(maos[lugar])} cartas", (x, y + 24), 15, comum_TXT, "center", False)
        mostrar = vaza_vista if fase == "pausa" else vaza
        for lugar, carta in mostrar:
            x, y = posicoes_vaza[lugar]
            r = pygame.Rect(0, 0, 64, 90)
            r.center = (x, y)
            destaque = (250, 210, 90) if fase == "pausa" and lugar == vencedor_vaza else (110, 110, 110)
            nexus_desenhar_carta(pygame, screen, r, carta, destaque, mostrar_pontos=False)
        if fase != "fim":
            mx, my = pygame.mouse.get_pos()
            for carta, r in zip(maos[0], rects_mao()):
                pode = fase == "jogar" and jogador == 0 and carta in legais
                caixa = r.copy()
                if pode and r.collidepoint((mx, my)):
                    caixa.y -= 14
                nexus_desenhar_carta(pygame, screen, caixa, carta, (70, 180, 120) if pode else (110, 110, 110))
        comum_texto(screen, msg, (cx, 706), 17, comum_TXT, "center", False)
        if fase == "fim":
            final = {"win": "VITÓRIA DA TUA EQUIPA", "loss": "A ATHENA GANHOU", "draw": "EMPATE (60 — 60)"}[veredito()]
            pygame.draw.rect(screen, (12, 18, 24), (320, 250, 600, 150), border_radius=14)
            comum_texto(screen, final, (cx, 300), 34, comum_OURO, "center")
            comum_texto(screen, f"{pontos[0]} — {pontos[1]}", (cx, 345), 24, comum_TXT, "center")
            comum_texto(screen, "Clica para continuar  |  ESC para sair", (cx, 380), 15, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)


# UNO — duelo contra a ATHENA (versão simplificada, sem inversão)
nexus_UNO_CORES = ["VERMELHO", "AZUL", "VERDE", "AMARELO"]
nexus_UNO_RGB = [(205, 55, 55), (55, 105, 205), (45, 155, 85), (225, 185, 45)]
nexus_UNO_ROXO = (110, 80, 150)


def nexus_uno_baralho(rng):
    deck = []
    for c in range(4):
        deck.append((c, "0"))
        for v in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "+2", "BLOQ"]:
            deck.extend([(c, v), (c, v)])
    for v in ["COR", "+4"]:
        deck.extend([(-1, v)] * 4)
    rng.shuffle(deck)
    return deck


def nexus_uno_base(carta, mao, adversario):
    cor, valor = carta
    s = 0.0
    if valor in ("+2", "BLOQ"):
        s += 1.5 + (1.5 if adversario <= 2 else 0.0)
    elif valor == "+4":
        s += 2.5 if adversario <= 2 else -1.0
    elif valor == "COR":
        s -= 0.8
    else:
        s += 0.3
    if cor >= 0:
        s += 0.4 * sum(1 for x in mao if x[0] == cor) / max(1, len(mao))
    return s


def nexus_uno_jogar(screen, clock):
    import pygame
    rng = _random.Random()
    deck = nexus_uno_baralho(rng)
    maos = [deck[:7], deck[7:14]]
    del deck[:14]
    topo = deck.pop()
    while topo[0] < 0:                       # a primeira carta virada nunca é um coringa
        deck.insert(0, topo)
        topo = deck.pop()
    descarte = [topo]
    ativa = topo[0]
    turno = 0
    fase = "jogar"                           # jogar | cor | fim
    pendente = None                          # coringa do jogador à espera da escolha da cor
    resultado = None
    msg = "Joga uma carta da mesma cor ou do mesmo valor."
    pronto_em = 0
    nexus_athena_nova_partida("uno")
    BTN_COMPRAR = pygame.Rect(850, 190, 120, 168)
    BTNS_COR = [pygame.Rect(420 + i * 100, 300, 90, 70) for i in range(4)]

    def comprar(quem):
        nonlocal deck
        if not deck:
            cima = descarte[-1]
            resto = descarte[:-1]
            rng.shuffle(resto)
            deck = resto
            descarte[:] = [cima]
        if deck:
            maos[quem].append(deck.pop())
            return True
        return False

    def legal(carta):
        return carta[0] == -1 or carta[0] == ativa or carta[1] == descarte[-1][1]

    def aplicar(carta, quem, cor=None):
        nonlocal ativa, turno, msg, resultado, fase, pronto_em
        maos[quem].remove(carta)
        descarte.append(carta)
        nome = nexus_UNO_CORES[carta[0]] + " " if carta[0] >= 0 else ""
        nexus_athena_record_move("uno", "jogador" if quem == 0 else "ATHENA", f"jogou {nome}{carta[1]}")
        if carta[0] >= 0:
            ativa = carta[0]
        elif cor is not None:
            ativa = cor
        elif maos[quem]:
            ativa = max(range(4), key=lambda c: sum(1 for x in maos[quem] if x[0] == c))
        else:
            ativa = rng.randrange(4)
        pronto_em = pygame.time.get_ticks() + 900
        if not maos[quem]:
            resultado = "win" if quem == 0 else "loss"
            fase = "fim"
            return
        outro = 1 - quem
        quem_nome = "Tu" if quem == 0 else "A ATHENA"
        if carta[1] == "+2":
            comprar(outro), comprar(outro)
            turno = quem
            msg = f"{quem_nome} jogou +2: o adversário compra duas cartas e perde a vez."
        elif carta[1] == "+4":
            for _ in range(4):
                comprar(outro)
            turno = quem
            msg = f"{quem_nome} jogou +4 e escolheu {nexus_UNO_CORES[ativa]}: quatro cartas compradas."
        elif carta[1] == "BLOQ":
            turno = quem
            msg = f"{quem_nome} bloqueou a vez do adversário."
        else:
            turno = outro
            msg = "UNO! Só resta uma carta." if len(maos[quem]) == 1 else (
                "Boa jogada." if quem == 0 else f"A ATHENA jogou. Cor ativa: {nexus_UNO_CORES[ativa]}.")
            if carta[0] == -1:
                msg = f"{quem_nome} escolheu a cor {nexus_UNO_CORES[ativa]}."

    def rects_mao():
        n = len(maos[0])
        passo = min(92, (1100 - 84) // max(1, n - 1)) if n > 1 else 0
        total = (n - 1) * passo + 84 if n else 0
        x0 = (comum_W - total) // 2
        return [pygame.Rect(x0 + i * passo, 450, 84, 122) for i in range(n)]

    while True:
        agora = pygame.time.get_ticks()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                elif e.key == pygame.K_ESCAPE:
                    if fase == "cor":
                        fase, pendente = "jogar", None
                        msg = "Escolha de cor cancelada."
                    else:
                        return None if fase != "fim" else resultado
                elif fase == "fim" and e.key == pygame.K_RETURN:
                    return resultado
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if fase == "fim":
                    return resultado
                if fase == "cor":
                    for i, r in enumerate(BTNS_COR):
                        if r.collidepoint(e.pos):
                            carta = pendente
                            fase, pendente = "jogar", None
                            aplicar(carta, 0, i)
                    continue
                if fase == "jogar" and turno == 0:
                    if BTN_COMPRAR.collidepoint(e.pos):
                        if comprar(0):
                            nexus_athena_record_move("uno", "jogador", "comprou uma carta")
                            turno = 1
                            pronto_em = agora + 900
                            msg = "Compraste uma carta e passaste a vez."
                        continue
                    for i in reversed(range(len(maos[0]))):
                        if rects_mao()[i].collidepoint(e.pos):
                            carta = maos[0][i]
                            if not legal(carta):
                                msg = "Essa carta não corresponde à cor nem ao valor."
                            elif carta[0] == -1 and len(maos[0]) > 1:
                                fase, pendente = "cor", carta
                                msg = "Escolhe a nova cor."
                            else:
                                aplicar(carta, 0)
                            break
        if fase == "jogar" and turno == 1 and agora >= pronto_em:
            escolhas = [c for c in maos[1] if legal(c)]
            if escolhas:
                bases = [nexus_uno_base(c, maos[1], len(maos[0])) for c in escolhas]
                carta = nexus_cerebro().choose("uno", escolhas, (maos[1], ativa, descarte[-1], len(deck)), bases)
                aplicar(carta, 1)
            else:
                comprar(1)
                nexus_athena_record_move("uno", "ATHENA", "comprou uma carta")
                turno = 0
                msg = "A ATHENA não tinha jogada e comprou uma carta."
        # ------------------------------------------------------------ desenho
        screen.fill((20, 25, 32))
        cx = nexus_centro_x()
        comum_texto(screen, "NEXUS / UNO", (cx, 36), 30, comum_OURO, "center")
        comum_texto(screen, f"COR ATIVA: {nexus_UNO_CORES[ativa]}", (cx, 86), 22, nexus_UNO_RGB[ativa], "center")
        comum_texto(screen, f"ATHENA: {len(maos[1])} cartas", (cx, 124), 17, comum_TXT, "center", False)
        n_ia = min(len(maos[1]), 16)
        for i in range(n_ia):
            pygame.draw.rect(screen, (60, 66, 90), (cx - n_ia * 17 + i * 34, 148, 30, 42), border_radius=5)
            pygame.draw.rect(screen, (110, 120, 160), (cx - n_ia * 17 + i * 34, 148, 30, 42), 2, border_radius=5)
        cima = descarte[-1]
        cor_cima = nexus_UNO_RGB[cima[0]] if cima[0] >= 0 else nexus_UNO_ROXO
        pygame.draw.rect(screen, cor_cima, (cx - 65, 206, 130, 160), border_radius=14)
        pygame.draw.rect(screen, (255, 255, 255), (cx - 65, 206, 130, 160), 3, border_radius=14)
        comum_texto(screen, cima[1], (cx, 286), 34, (255, 255, 255), "center")
        pygame.draw.rect(screen, (65, 90, 130) if (fase == "jogar" and turno == 0) else (48, 56, 74), BTN_COMPRAR, border_radius=12)
        comum_texto(screen, "COMPRAR", BTN_COMPRAR.center, 17, comum_TXT, "center")
        comum_texto(screen, f"({len(deck)})", (BTN_COMPRAR.centerx, BTN_COMPRAR.centery + 24), 14, comum_DIM, "center", False)
        mx, my = pygame.mouse.get_pos()
        for i, (carta, r) in enumerate(zip(maos[0], rects_mao())):
            pode = fase == "jogar" and turno == 0 and legal(carta)
            caixa = r.copy()
            if pode and r.collidepoint((mx, my)) and not any(rr.collidepoint((mx, my)) for rr in rects_mao()[i + 1:]):
                caixa.y -= 14
            pygame.draw.rect(screen, nexus_UNO_RGB[carta[0]] if carta[0] >= 0 else nexus_UNO_ROXO, caixa, border_radius=9)
            pygame.draw.rect(screen, (250, 210, 90) if pode else (20, 20, 26), caixa, 3, border_radius=9)
            comum_texto(screen, carta[1], caixa.center, 20, (255, 255, 255), "center")
        comum_texto(screen, f"TU: {len(maos[0])} cartas", (cx, 600), 17, comum_TXT, "center", False)
        if fase == "cor":
            pygame.draw.rect(screen, (14, 18, 26), (380, 250, 480, 150), border_radius=12)
            comum_texto(screen, "ESCOLHE A COR", (cx, 272), 18, comum_OURO, "center")
            for i, r in enumerate(BTNS_COR):
                pygame.draw.rect(screen, nexus_UNO_RGB[i], r, border_radius=10)
        comum_texto(screen, msg, (cx, 676), 17, comum_TXT, "center", False)
        if fase == "fim":
            pygame.draw.rect(screen, (12, 16, 22), (340, 250, 560, 160), border_radius=14)
            comum_texto(screen, "GANHASTE" if resultado == "win" else "A ATHENA GANHOU", (cx, 305), 34, comum_OURO, "center")
            comum_texto(screen, "Clica para regressar ao NEXUS", (cx, 360), 16, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)


# NEXUS PROPRIEDADES — compra, rendas e economia contra a ATHENA
nexus_PROP_CASAS = [("NEXUS START", 0, 0), ("ARQUIVO AZUL", 120, 25), ("DADOS", 0, 0), ("TORRE VERDE", 150, 30),
               ("AUDITORIA", 0, 0), ("LABORATÓRIO", 180, 36), ("PAUSA", 0, 0), ("SERVIDOR RUBI", 210, 42),
               ("BUG DE SISTEMA", 0, 0), ("CENTRO NEXUS", 240, 48), ("CRIPTOGRAFIA", 270, 54),
               ("NÚCLEO ATHENA", 320, 64)]


def nexus_propriedades_jogar(screen, clock):
    import pygame
    rng = _random.Random()
    casas = nexus_PROP_CASAS
    n = len(casas)
    cash = [1000, 1000]
    pos = [0, 0]
    dono = [None] * n
    rondas = 0
    turno = 0
    pendente = None
    resultado = None
    msg = "Lança os dados e constrói o teu império."
    pronto_em = 0
    ultimo_lancamento = None
    nexus_athena_nova_partida("propriedades")
    BTN_LANCAR = pygame.Rect(520, 570, 200, 65)
    BTN_COMPRAR = pygame.Rect(760, 570, 180, 65)
    BTN_PASSAR = pygame.Rect(970, 570, 180, 65)

    def pontuacao(i):
        return cash[i] + sum(casas[j][1] // 2 for j in range(n) if dono[j] == i)

    def verificar_fim():
        nonlocal resultado
        if resultado is not None:
            return
        for quem in (0, 1):
            if cash[quem] < 0:
                resultado = "loss" if quem == 0 else "win"
                return
        if rondas >= 24:
            a, b = pontuacao(0), pontuacao(1)
            resultado = "win" if a > b else "loss" if b > a else "draw"

    def mover(quem, passos):
        nonlocal msg, pendente, rondas, turno, pronto_em, ultimo_lancamento
        antigo = pos[quem]
        pos[quem] = (antigo + passos) % n
        nome, preco, renda = casas[pos[quem]]
        sujeito = "Tu" if quem == 0 else "A ATHENA"
        ultimo_lancamento = passos
        partes = [f"{sujeito}: {passos} casas → {nome}."]
        nexus_athena_record_move("propriedades", "jogador" if quem == 0 else "ATHENA", f"lançou {passos}; avançou para {nome}")
        if pos[quem] < antigo:
            cash[quem] += 100
            partes.append("START: +100 créditos.")
        if preco:
            if dono[pos[quem]] is None:
                if quem == 0:
                    if cash[0] >= preco:
                        pendente = pos[0]
                        partes.append(f"Custa {preco}. Comprar?")
                    else:
                        partes.append(f"Custa {preco}; não tens créditos suficientes.")
                elif cash[1] >= preco:
                    possui = sum(1 for j in range(n) if dono[j] == 1)
                    pontuacao_compra = renda * 2.2 - preco * 0.18 + (cash[1] - preco) * 0.025 - possui * 4
                    estado = (cash[1], preco, renda, possui, pos[1])
                    compra = nexus_cerebro().choose("propriedades", [False, True], estado, [0.0, pontuacao_compra])
                    if compra:
                        cash[1] -= preco
                        dono[pos[1]] = 1
                        nexus_athena_record_move("propriedades", "ATHENA", f"comprou {nome} por {preco} créditos")
                        partes.append(f"A ATHENA comprou {nome}.")
                    else:
                        partes.append("A ATHENA decidiu conservar os créditos.")
            elif dono[pos[quem]] != quem:
                cash[quem] -= renda
                cash[dono[pos[quem]]] += renda
                partes.append(f"{'Pagaste' if quem == 0 else 'A ATHENA pagou'} {renda} créditos de renda.")
        elif pos[quem] in (2, 8):
            delta = rng.choice([-100, -60, 80, 120])
            cash[quem] += delta
            partes.append(f"Evento de sistema: {delta:+d} créditos.")
        elif pos[quem] == 4:
            cash[quem] -= 50
            partes.append("Auditoria: -50 créditos.")
        msg = " ".join(partes)
        if pendente is None:
            turno = 1 - quem
            if quem == 1:
                rondas += 1
            pronto_em = pygame.time.get_ticks() + 1000
        verificar_fim()

    def terminar_decisao(comprou):
        nonlocal pendente, turno, msg, pronto_em
        casa = pendente
        nome, preco, _ = casas[casa]
        if comprou:
            cash[0] -= preco
            dono[casa] = 0
            nexus_athena_record_move("propriedades", "jogador", f"comprou {nome} por {preco} créditos")
            msg = f"Compraste {nome}."
        else:
            nexus_athena_record_move("propriedades", "jogador", f"recusou comprar {nome}")
            msg = "Decidiste não comprar."
        pendente = None
        turno = 1
        pronto_em = pygame.time.get_ticks() + 900

    while True:
        agora = pygame.time.get_ticks()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                elif e.key == pygame.K_ESCAPE:
                    return None if resultado is None else resultado
                elif resultado is not None and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return resultado
                elif resultado is None and turno == 0 and pendente is None and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    mover(0, rng.randint(1, 6) + rng.randint(1, 6))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if resultado is not None:
                    return resultado
                if turno != 0:
                    continue
                if pendente is not None:
                    if BTN_COMPRAR.collidepoint(e.pos):
                        terminar_decisao(True)
                    elif BTN_PASSAR.collidepoint(e.pos):
                        terminar_decisao(False)
                elif BTN_LANCAR.collidepoint(e.pos):
                    mover(0, rng.randint(1, 6) + rng.randint(1, 6))
        if resultado is None and turno == 1 and pendente is None and agora >= pronto_em:
            mover(1, rng.randint(1, 6) + rng.randint(1, 6))
        # ------------------------------------------------------------ desenho
        screen.fill((20, 25, 33))
        cx = nexus_centro_x()
        comum_texto(screen, "NEXUS PROPRIEDADES", (cx, 35), 30, comum_OURO, "center")
        comum_texto(screen, f"TU: {cash[0]} créditos", (260, 100), 22, comum_TXT, "center")
        comum_texto(screen, f"ATHENA: {cash[1]} créditos", (980, 100), 22, comum_TXT, "center")
        comum_texto(screen, f"Ronda {min(rondas + 1, 24)}/24", (cx, 100), 16, comum_DIM, "center", False)
        for i, (nome, preco, renda) in enumerate(casas):
            x = 115 + (i % 4) * 270
            y = 175 + (i // 4) * 112
            rect = pygame.Rect(x, y, 235, 78)
            pygame.draw.rect(screen, (45, 55, 72), rect, border_radius=8)
            cor = (80, 190, 120) if dono[i] == 0 else (205, 85, 85) if dono[i] == 1 else (120, 130, 145)
            pygame.draw.rect(screen, cor, rect, 3, border_radius=8)
            comum_texto(screen, nome, (x + 117, y + 22), 15, comum_TXT, "center")
            if preco:
                comum_texto(screen, f"{preco} / renda {renda}", (x + 117, y + 51), 12, comum_DIM, "center", False)
            if pos[0] == i:
                comum_texto(screen, "TU", (x + 22, y + 65), 11, (120, 220, 150), "center", False)
            if pos[1] == i:
                comum_texto(screen, "IA", (x + 210, y + 65), 11, (240, 130, 130), "center", False)
        if resultado is None:
            if pendente is None:
                ativo = turno == 0
                pygame.draw.rect(screen, (65, 95, 135) if ativo else (45, 52, 68), BTN_LANCAR, border_radius=9)
                comum_texto(screen, "LANÇAR DADOS" if ativo else "A ATHENA JOGA...", BTN_LANCAR.center, 17, comum_TXT, "center")
            else:
                pygame.draw.rect(screen, (60, 135, 90), BTN_COMPRAR, border_radius=9)
                comum_texto(screen, "COMPRAR", BTN_COMPRAR.center, 18, comum_TXT, "center")
                pygame.draw.rect(screen, (110, 70, 75), BTN_PASSAR, border_radius=9)
                comum_texto(screen, "PASSAR", BTN_PASSAR.center, 18, comum_TXT, "center")
        comum_texto(screen, msg, (cx, 680), 16, comum_TXT, "center", False)
        if resultado is not None:
            pygame.draw.rect(screen, (14, 18, 26), (340, 230, 560, 170), border_radius=14)
            texto = {"win": "GANHASTE", "loss": "A ATHENA GANHOU", "draw": "EMPATE"}[resultado]
            comum_texto(screen, texto, (cx, 290), 36, comum_OURO, "center")
            comum_texto(screen, f"Património: tu {pontuacao(0)}  —  ATHENA {pontuacao(1)}", (cx, 340), 18, comum_TXT, "center", False)
            comum_texto(screen, "Clica para continuar", (cx, 375), 15, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)


# ATHENA — comentários gerados em tempo real pelo modelo local (Ollama)
# Não existem frases pré-escritas: se o Ollama não responder, a ATHENA fica calada
# (e o ecrã mostra o estado da IA).
nexus_ATHENA_OLLAMA_MODEL = os.environ.get("ATHENA_OLLAMA_MODEL", "llama3.2:3b")
nexus_ATHENA_OLLAMA_URL = os.environ.get("ATHENA_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
nexus_OLLAMA_BASE = nexus_ATHENA_OLLAMA_URL.rsplit("/api/", 1)[0]

# Estado da ligação ao Ollama: 'A VERIFICAR' | 'ONLINE' | 'OFFLINE' | 'SEM MODELO'
nexus_OLLAMA_ESTADO = {"texto": "A VERIFICAR", "ate": 0.0}


nexus_OLLAMA_LOCK = _threading.Lock()


def nexus_athena_ollama(prompt, timeout=40, max_tokens=110, json_mode=False, esperar=False):
    if _time.time() < nexus_OLLAMA_ESTADO["ate"] and nexus_OLLAMA_ESTADO["texto"] != "ONLINE":
        raise RuntimeError("Ollama indisponível (nova tentativa em breve).")
    obtido = nexus_OLLAMA_LOCK.acquire(timeout=240) if esperar else nexus_OLLAMA_LOCK.acquire(blocking=False)
    if not obtido:
        raise RuntimeError("O modelo está ocupado com outro pedido.")
    try:
        return nexus_athena_ollama_pedido(prompt, timeout, max_tokens, json_mode)
    finally:
        nexus_OLLAMA_LOCK.release()


def nexus_athena_ollama_pedido(prompt, timeout, max_tokens, json_mode):
    payload = {
        "model": nexus_ATHENA_OLLAMA_MODEL, "prompt": prompt, "stream": True, "keep_alive": "20m",
        "options": {"temperature": 0.7 if json_mode else 0.85, "top_p": 0.92, "num_predict": max_tokens, "num_ctx": 4096},
    }
    if json_mode:
        payload["format"] = "json"
    req = urllib.request.Request(nexus_ATHENA_OLLAMA_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    partes = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            for linha in response:
                if not linha.strip():
                    continue
                bloco = json.loads(linha.decode("utf-8"))
                if bloco.get("error"):
                    raise RuntimeError("Ollama: " + str(bloco["error"])[:80])
                partes.append(str(bloco.get("response", "")))
                if bloco.get("done"):
                    break
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            nexus_OLLAMA_ESTADO.update(texto="SEM MODELO", ate=_time.time() + 30)
        raise RuntimeError(f"Ollama devolveu erro HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):      # lento != offline
            raise RuntimeError("O modelo demorou demasiado a responder.") from exc
        nexus_OLLAMA_ESTADO.update(texto="OFFLINE", ate=_time.time() + 20)
        raise RuntimeError("Ollama não responde: " + str(exc)) from exc
    except (socket.timeout, TimeoutError) as exc:                          # lento != offline
        raise RuntimeError("O modelo demorou demasiado a responder.") from exc
    except (ConnectionError, OSError) as exc:
        nexus_OLLAMA_ESTADO.update(texto="OFFLINE", ate=_time.time() + 20)
        raise RuntimeError("Ollama não responde: " + str(exc)) from exc
    nexus_OLLAMA_ESTADO.update(texto="ONLINE", ate=0.0)
    resposta = "".join(partes).strip()
    if not resposta:
        raise RuntimeError("Ollama devolveu uma resposta vazia.")
    return resposta


def nexus_verificar_ollama():
    def trabalho():
        try:
            with urllib.request.urlopen(nexus_OLLAMA_BASE + "/api/tags", timeout=3) as r:
                modelos = [m.get("name", "") for m in json.loads(r.read().decode("utf-8")).get("models", [])]
            base = nexus_ATHENA_OLLAMA_MODEL.split(":")[0]
            if any(m == nexus_ATHENA_OLLAMA_MODEL or m.startswith(nexus_ATHENA_OLLAMA_MODEL + ":") or
                   (":" not in nexus_ATHENA_OLLAMA_MODEL and m.split(":")[0] == base) for m in modelos):
                nexus_OLLAMA_ESTADO.update(texto="ONLINE", ate=0.0)
                try:                                   # carrega o modelo já, para o 1.º comentário/análise não demorar
                    aquece = urllib.request.Request(nexus_ATHENA_OLLAMA_URL, method="POST", headers={"Content-Type": "application/json"},
                                                    data=json.dumps({"model": nexus_ATHENA_OLLAMA_MODEL, "keep_alive": "20m"}).encode("utf-8"))
                    urllib.request.urlopen(aquece, timeout=180).read()
                except Exception:
                    pass
            else:
                nexus_OLLAMA_ESTADO.update(texto="SEM MODELO", ate=0.0)
                print(f"[ATHENA IA] Modelo '{nexus_ATHENA_OLLAMA_MODEL}' não instalado. Executa: ollama pull {nexus_ATHENA_OLLAMA_MODEL}")
        except Exception:
            nexus_OLLAMA_ESTADO.update(texto="OFFLINE", ate=0.0)
            print("[ATHENA IA] Ollama não está a responder: a ATHENA jogará sem comentários nem análise detalhada.")
    _threading.Thread(target=trabalho, daemon=True, name="ATHENA-VerificaOllama").start()


def nexus_limpar_fala(texto):
    t = str(texto).replace("\n", " ").replace("*", "").replace("_", " ").replace("#", "").strip().strip('"“”«»\'')
    t = " ".join(t.split())
    if len(t) > 300:
        corte = max(t.rfind(".", 0, 300), t.rfind("!", 0, 300), t.rfind("?", 0, 300))
        t = t[:corte + 1] if corte > 60 else t[:300].rsplit(" ", 1)[0] + "."
    if t and t[-1] not in ".!?…":                 # o modelo parou a meio: corta na última frase completa
        corte = max(t.rfind(".", 0), t.rfind("!", 0), t.rfind("?", 0))
        t = t[:corte + 1] if corte >= 15 else t.rstrip(",;:- ") + "."
    return t


def nexus_extrair_json(bruto):
    try:
        return json.loads(bruto.strip())
    except Exception:
        pass
    a, b = bruto.find("{"), bruto.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("A resposta não contém JSON.")
    return json.loads(bruto[a:b + 1])


nexus_PS_VOZ = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $melhor = $null; $pts = 0
  foreach ($v in $s.GetInstalledVoices()) {
    if (-not $v.Enabled) { continue }
    $c = $v.VoiceInfo.Culture.Name.ToLower()
    $p = 0
    if ($c -eq 'pt-pt') { $p = 3 } elseif ($c.StartsWith('pt')) { $p = 2 }
    if ($p -gt $pts) { $pts = $p; $melhor = $v.VoiceInfo.Name }
  }
  if ($melhor) { $s.SelectVoice($melhor) }
  $s.SetOutputToDefaultAudioDevice()
  $s.Rate = 1
  $s.Volume = 100
  [Console]::Out.WriteLine('PRONTO ' + $s.Voice.Name)
} catch {
  [Console]::Out.WriteLine('FALHA ' + $_.Exception.Message)
  [Console]::Out.Flush()
  exit 1
}
[Console]::Out.Flush()
while ($true) {
  $linha = [Console]::In.ReadLine()
  if ($linha -eq $null) { break }
  if ($linha.Trim().Length -eq 0) { continue }
  try {
    $texto = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($linha.Trim()))
    $s.Speak($texto)
    [Console]::Out.WriteLine('FIM')
  } catch {
    [Console]::Out.WriteLine('ERRO ' + $_.Exception.Message)
  }
  [Console]::Out.Flush()
}
"""

nexus_VBS_VOZ = """Set v = CreateObject("SAPI.SpVoice")
For Each t In v.GetVoices
  d = LCase(t.GetDescription)
  If InStr(d, "portug") > 0 Or InStr(d, "helia") > 0 Or InStr(d, "joana") > 0 Or InStr(d, "maria") > 0 Then
    Set v.Voice = t
    Exit For
  End If
Next
Set fso = CreateObject("Scripting.FileSystemObject")
Set f = fso.OpenTextFile(WScript.Arguments(0), 1, False, -1)
txt = f.ReadAll
f.Close
v.Volume = 100
v.Speak txt
"""


def nexus_log_voz(txt):
    try:
        with open(os.path.join(nexus_AQUI, "athena_voz.log"), "a", encoding="utf-8") as f:
            f.write(_time.strftime("%H:%M:%S ") + str(txt) + "\n")
    except Exception:
        pass


class nexus_VozPowerShell:
    SCRIPT = nexus_PS_VOZ

    def __init__(self):
        cod = base64.b64encode(self.SCRIPT.encode("utf-16-le")).decode("ascii")
        self.proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", cod],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._iniciar_leitor()
        try:
            pronto = self._resposta(25)
        except Exception as exc:
            self.parar()
            raise RuntimeError(str(exc))
        if not pronto.startswith("PRONTO"):
            self.parar()
            raise RuntimeError(pronto[:80] or "o PowerShell não respondeu")
        self.nome = pronto.replace("PRONTO", "").strip()

    def falar(self, frase):
        linha = base64.b64encode(" ".join(frase.split()).encode("utf-8")) + b"\n"
        self.proc.stdin.write(linha)
        self.proc.stdin.flush()
        resp = self._resposta(90)
        if not resp:
            raise RuntimeError("O PowerShell da voz terminou")
        if resp.startswith("ERRO"):
            raise RuntimeError(resp[:80])

    def _iniciar_leitor(self):
        self._linhas = _queue.Queue()

        def ler():
            try:
                for bruto in iter(self.proc.stdout.readline, b""):
                    self._linhas.put(bruto.decode("utf-8", "replace").lstrip("\ufeff").strip())
            except Exception:
                pass
            finally:
                self._linhas.put(None)
        _threading.Thread(target=ler, daemon=True, name="ATHENA-LeVoz").start()

    def _resposta(self, espera):
        try:
            r = self._linhas.get(timeout=espera)
        except _queue.Empty:
            raise RuntimeError("o PowerShell não respondeu a tempo")
        if r is None:
            raise RuntimeError("o PowerShell terminou")
        return r

    def parar(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


nexus_PS_WAV = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $melhor = $null; $pts = 0
  foreach ($v in $s.GetInstalledVoices()) {
    if (-not $v.Enabled) { continue }
    $c = $v.VoiceInfo.Culture.Name.ToLower()
    $p = 0
    if ($c -eq 'pt-pt') { $p = 3 } elseif ($c.StartsWith('pt')) { $p = 2 }
    if ($p -gt $pts) { $pts = $p; $melhor = $v.VoiceInfo.Name }
  }
  if ($melhor) { $s.SelectVoice($melhor) }
  $s.Rate = 1
  [Console]::Out.WriteLine('PRONTO ' + $s.Voice.Name)
} catch {
  [Console]::Out.WriteLine('FALHA ' + $_.Exception.Message)
  [Console]::Out.Flush()
  exit 1
}
[Console]::Out.Flush()
while ($true) {
  $linha = [Console]::In.ReadLine()
  if ($linha -eq $null) { break }
  if ($linha.Trim().Length -eq 0) { continue }
  try {
    $partes = $linha.Trim().Split('|')
    $caminho = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($partes[0]))
    $texto = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($partes[1]))
    $s.SetOutputToWaveFile($caminho)
    $s.Speak($texto)
    $s.SetOutputToNull()
    [Console]::Out.WriteLine('FIM')
  } catch {
    try { $s.SetOutputToNull() } catch {}
    [Console]::Out.WriteLine('ERRO ' + $_.Exception.Message)
  }
  [Console]::Out.Flush()
}
"""


class nexus_VozWav(nexus_VozPowerShell):
    SCRIPT = nexus_PS_WAV

    def __init__(self):
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="athena_wav_")
        self._n = 0
        super().__init__()

    def falar(self, frase):
        import pygame
        self._n += 1
        caminho = os.path.join(self.dir, f"fala_{self._n}.wav")
        linha = (base64.b64encode(caminho.encode("utf-8")) + b"|" +
                 base64.b64encode(" ".join(frase.split()).encode("utf-8")) + b"\n")
        self.proc.stdin.write(linha)
        self.proc.stdin.flush()
        resp = self._resposta(90)
        if not resp:
            raise RuntimeError("O PowerShell da voz terminou")
        if resp.startswith("ERRO"):
            raise RuntimeError(resp[:80])
        if not os.path.exists(caminho) or os.path.getsize(caminho) < 2000:
            raise RuntimeError("o áudio gerado está vazio")
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        som = pygame.mixer.Sound(caminho)
        som.set_volume(1.0)
        canal = som.play()
        while canal is not None and canal.get_busy():
            _time.sleep(0.05)
        try:
            os.remove(caminho)
        except OSError:
            pass


class nexus_VozVbs:
    nome = "SAPI (cscript)"

    def __init__(self):
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="athena_voz_")
        self.vbs = os.path.join(self.dir, "falar.vbs")
        self.txt = os.path.join(self.dir, "texto.txt")
        with open(self.vbs, "w", encoding="utf-16") as f:
            f.write(nexus_VBS_VOZ)

    def falar(self, frase):
        with open(self.txt, "w", encoding="utf-16") as f:
            f.write(" ".join(frase.split()))
        r = subprocess.run(["cscript", "//nologo", self.vbs, self.txt], capture_output=True, timeout=min(25, 8 + len(frase) * 0.12),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or b"cscript falhou").decode("utf-8", "replace").strip()[:80])

    def parar(self):
        pass


nexus_PS_UNICA = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$melhor = $null; $pts = 0
foreach ($v in $s.GetInstalledVoices()) {
  if (-not $v.Enabled) { continue }
  $c = $v.VoiceInfo.Culture.Name.ToLower()
  $p = 0
  if ($c -eq 'pt-pt') { $p = 3 } elseif ($c.StartsWith('pt')) { $p = 2 }
  if ($p -gt $pts) { $pts = $p; $melhor = $v.VoiceInfo.Name }
}
if ($melhor) { $s.SelectVoice($melhor) }
$s.Volume = 100
$t = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:ATHENA_TXT))
$s.Speak($t)
"""


class nexus_VozUnica:
    nome = "Windows"

    def falar(self, frase):
        cod = base64.b64encode(nexus_PS_UNICA.encode("utf-16-le")).decode("ascii")
        env = dict(os.environ)
        env["ATHENA_TXT"] = base64.b64encode(" ".join(frase.split()).encode("utf-8")).decode("ascii")
        t0 = _time.time()
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-EncodedCommand", cod], env=env, capture_output=True, timeout=min(25, 8 + len(frase) * 0.12),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or b"powershell falhou").decode("utf-8", "replace").strip()[:80])
        if len(frase) > 30 and _time.time() - t0 < 0.5:
            raise RuntimeError("o Windows não produziu som")


nexus_ATHENA_USAR_NEURAL = False                  # voz local do Windows: evita espera de síntese online antes de falar
nexus_ATHENA_VOZ_EDGE = "pt-PT-RaquelNeural"      # voz neural portuguesa (alternativa masculina: pt-PT-DuarteNeural)


class nexus_VozEdge:

    def __init__(self):
        import edge_tts, pygame, tempfile      # ImportError -> esta voz fica desligada
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self.voz = nexus_ATHENA_VOZ_EDGE
        self.nome = self.voz.replace("Neural", "").replace("pt-PT-", "") + " (neural)"
        self.dir = tempfile.mkdtemp(prefix="athena_edge_")
        self._n = 0

    async def _gerar(self, texto, caminho):
        import asyncio, edge_tts
        await asyncio.wait_for(edge_tts.Communicate(texto, self.voz).save(caminho), timeout=12)

    def falar(self, frase):
        import asyncio, pygame
        self._n += 1
        caminho = os.path.join(self.dir, f"fala_{self._n}.mp3")
        asyncio.run(self._gerar(" ".join(frase.split()), caminho))
        if not os.path.exists(caminho) or os.path.getsize(caminho) < 1500:
            raise RuntimeError("a voz neural devolveu áudio vazio")
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        t_ini = _time.time()
        try:
            som = pygame.mixer.Sound(caminho)
            canal = som.play()
            while canal is not None and canal.get_busy():
                _time.sleep(0.05)
        except Exception:
            pygame.mixer.music.load(caminho)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                _time.sleep(0.05)
            pygame.mixer.music.unload()
        if len(frase) > 30 and _time.time() - t_ini < 0.5:
            raise RuntimeError("o áudio não tocou (mixer sem saída?)")
        try:
            os.remove(caminho)
        except OSError:
            pass

    def parar(self):
        pass


class nexus_ATHENAAnnouncer:
    NOME_JOGOS = {"quatro": "Quatro em Linha", "damas": "Damas", "bilhar": "Bilhar", "xadrez": "Xadrez",
                  "sueca": "Sueca"}

    def __init__(self):
        # Todo o estado é criado ANTES de arrancar a thread da voz (que o usa).
        self._queue = _queue.Queue()
        self._stop = _threading.Event()
        self._speaking = _threading.Event()
        self._generation_lock = _threading.Lock()
        self._last_game = ""
        self._last_spoken_move_count = 0
        self._ultima_fala = 0.0
        self.last_error = ""
        self.legenda = None          # {"texto":..., "ate": None|timestamp} -> desenhada dentro do jogo
        self.voz_nome = ""
        self.voz_estado = "A INICIAR"
        self._voz = (None, None)
        self._ps_falhou = not sys.platform.startswith("win")
        self._py_tentado = False
        self._falhadas = {"wav"}                 # usa PowerShell persistente; evita iniciar um processo por cada frase
        self._edge = None
        self._unica = nexus_VozUnica()
        self._unica_ate = float("inf")  # usa primeiro o motor PowerShell persistente; evita um processo novo por frase
        self._edge_ate = 0.0           # depois desta hora volta a tentar a voz neural
        self._worker = _threading.Thread(target=self._voice_worker, daemon=True, name="ATHENA-Voz")
        self._worker.start()

    # --------------------------------------------------------------- voz
    def say(self, text):
        texto = nexus_limpar_fala(text)
        if not texto or self._stop.is_set():
            return
        while self._queue.qsize() >= 2:                # fala antiga já não interessa
            try:
                self._queue.get_nowait()
            except _queue.Empty:
                break
        self._queue.put(texto)

    def silenciar(self):
        while True:
            try:
                self._queue.get_nowait()
            except _queue.Empty:
                break

    def _criar_motor(self):
        for modulo in ("pythoncom", "comtypes"):       # SAPI5 numa thread precisa de COM inicializado
            try:
                mod = __import__(modulo)
                getattr(mod, "CoInitialize")()
                break
            except Exception:
                continue
        import pyttsx3
        try:
            engine = pyttsx3.init("sapi5")
        except Exception:
            engine = pyttsx3.init()                    # outros sistemas / drivers
        try:
            vozes = engine.getProperty("voices") or []
            melhor, pontos = None, 0
            for voz in vozes:
                info = (str(getattr(voz, "id", "")) + " " + str(getattr(voz, "name", "")) + " " +
                        str(getattr(voz, "languages", ""))).lower()
                p = (3 if ("pt-pt" in info or "portugal" in info or "helia" in info or "joana" in info) else
                     2 if "portuguese" in info else 1 if ("pt-br" in info or "brazil" in info) else 0)
                if p > pontos:
                    melhor, pontos = voz, p
            if melhor is not None:
                engine.setProperty("voice", melhor.id)
        except Exception:
            pass
        engine.setProperty("rate", 164)
        engine.setProperty("volume", 1.0)
        return engine

    def _iniciar_ps(self):
        for tipo, fabrica in (("wav", nexus_VozWav), ("ps", nexus_VozPowerShell), ("vbs", nexus_VozVbs)):
            if tipo in self._falhadas:
                continue
            try:
                voz = fabrica()
                self.voz_nome = voz.nome
                self._voz = (tipo, voz)
                self.voz_estado = "VOZ: " + (voz.nome or tipo) + (" (no jogo)" if tipo == "wav" else "")
                nexus_log_voz("voz ativa: " + tipo + " / " + str(voz.nome))
                return
            except Exception as exc:
                self._falhadas.add(tipo)
                self.last_error = tipo + ": " + str(exc)[:50]
                nexus_log_voz("falhou " + tipo + ": " + repr(exc))
        self._ps_falhou = True

    def _recomecar_voz(self, falhou=None):
        if falhou:
            self._falhadas.add(falhou)
        self._voz = (None, None)
        self.voz_estado = "A INICIAR"
        self._ps_falhou = not sys.platform.startswith("win")
        self._py_tentado = False
        if not self._ps_falhou:
            _threading.Thread(target=self._iniciar_ps, daemon=True, name="ATHENA-IniciaVoz").start()

    def _voice_worker(self):
        try:
            if not nexus_ATHENA_USAR_NEURAL:
                raise RuntimeError("desligada em ATHENA_USAR_NEURAL")
            self._edge = nexus_VozEdge()
            nexus_log_voz("voz neural disponível: " + self._edge.nome)
        except Exception as exc:
            self._edge = None
            nexus_log_voz("voz neural indisponível (pip install edge-tts): " + repr(exc))
        # Inicializa a voz antes de aceitar a primeira frase. Assim, a legenda nunca
        # fica à espera do arranque do PowerShell/SAPI.
        if not self._ps_falhou:
            self._iniciar_ps()
        while not self._stop.is_set():
            try:
                frase = self._queue.get(timeout=0.25)
            except _queue.Empty:
                continue
            if self._stop.is_set():
                break
            if not frase:
                continue
            nexus_log_voz("fala: " + frase[:70])
            if self._edge is not None and _time.time() >= self._edge_ate:
                self._speaking.set()
                self.legenda = {"texto": frase, "ate": _time.time() + 4 + len(frase) * 0.1}
                try:
                    self._edge.falar(frase)
                    self.voz_estado = "VOZ: " + self._edge.nome
                    continue
                except Exception as exc:
                    self._edge_ate = _time.time() + 90          # sem rede/erro: usa a voz do Windows e tenta de novo daqui a 90 s
                    self.last_error = "voz neural: " + str(exc)[:45]
                    nexus_log_voz("erro na voz neural: " + repr(exc))
                finally:
                    self._speaking.clear()
                    self.legenda = {"texto": frase, "ate": _time.time() + 2.5}
            if sys.platform.startswith("win") and _time.time() >= self._unica_ate:
                self._speaking.set()
                self.legenda = {"texto": frase, "ate": _time.time() + 4 + len(frase) * 0.1}
                try:
                    self._unica.falar(frase)
                    self.voz_estado = "VOZ: Windows"
                    nexus_log_voz("falou (powershell)")
                    continue
                except Exception as exc:
                    self._unica_ate = _time.time() + 20
                    nexus_log_voz("erro na voz do Windows (powershell): " + repr(exc))
                finally:
                    self._speaking.clear()
                    self.legenda = {"texto": frase, "ate": _time.time() + 2.5}
            if self._voz[0] is None and not self._ps_falhou:
                t0 = _time.time()                               # a voz do Windows ainda está a arrancar: espera (antes a 1.ª fala perdia-se)
                while (self._voz[0] is None and not self._ps_falhou and not self._stop.is_set()
                       and _time.time() - t0 < 12):
                    _time.sleep(0.1)
            if self._voz[0] is None and self._ps_falhou and not self._py_tentado:
                self._py_tentado = True                 # pyttsx3 tem de ser criado nesta thread
                try:
                    self._voz = ("py", self._criar_motor())
                    self.voz_estado = "VOZ: pyttsx3"
                except Exception as exc:
                    self.voz_estado = "SÓ LEGENDAS"
                    self.last_error = "pyttsx3: " + str(exc)[:55]
                    print("[ATHENA voz] Sem voz sintética (" + repr(exc) + "). A ATHENA fala só por legendas no jogo.")
            tipo, motor = self._voz
            self._speaking.set()
            self.legenda = {"texto": frase, "ate": _time.time() + 4 + len(frase) * 0.1}
            inicio = _time.time()
            try:
                if tipo in ("wav", "ps", "vbs"):
                    motor.falar(frase)
                elif tipo == "py":
                    motor.say(frase)
                    motor.runAndWait()
                else:
                    self.voz_estado = "SÓ LEGENDAS"
                    nexus_log_voz("sem motor de voz; legenda apresentada sem atraso artificial")
                if tipo == "ps" and len(frase) > 30 and _time.time() - inicio < 0.5:
                    # o PowerShell "falou" sem demorar: provavelmente sem áudio -> tenta a SAPI via cscript
                    self.last_error = "PowerShell sem som; a tentar SAPI"
                    motor.parar()
                    self._recomecar_voz(falhou="ps")
            except Exception as exc:
                self.last_error = "voz: " + str(exc)[:55]
                nexus_log_voz("erro a falar (" + str(tipo) + "): " + repr(exc))
                try:
                    if tipo in ("wav", "ps", "vbs"):
                        motor.parar()
                    elif tipo == "py":
                        motor.stop()
                except Exception:
                    pass
                self._recomecar_voz(falhou=tipo)
                _time.sleep(min(6.0, 1.0 + len(frase) * 0.05))
            finally:
                self._speaking.clear()
                self.legenda = {"texto": frase, "ate": _time.time() + 2.5}
        tipo, motor = self._voz
        try:
            if tipo in ("wav", "ps", "vbs"):
                motor.parar()
            elif tipo == "py":
                motor.stop()
        except Exception:
            pass

    def stop(self):
        self._stop.set()
        self.silenciar()
        self._queue.put("")

    # ------------------------------------------------------------ persona
    def _persona_prompt(self, game, context, instruction):
        return (
            "És ATHENA, uma inteligência artificial antagonista num jogo de estratégia. "
            "Falas diretamente com o jogador em português de Portugal. Personalidade: "
            "arrogante, calculista, fria, mordaz e inteligente; nunca uses insultos discriminatórios. "
            "Não faças perguntas, não esperes resposta e não digas que és um assistente. "
            "Cria texto ORIGINAL a partir dos dados fornecidos. Não uses frases genéricas nem bordões. "
            "Não inventes jogadas, peças, cartas ou acontecimentos que não estejam nos dados. "
            "Se os dados não provarem um erro, comenta apenas a decisão observável sem a chamar erro. "
            "Responde só com a fala, sem aspas, sem markdown e sem emojis. "
            f"Jogo: {self.NOME_JOGOS.get(game, game)}. Dados reais recentes: {context}. {instruction}")

    def nova_partida(self, game):
        self._last_spoken_move_count = 0

    def begin_game(self, game):
        mic = globals().get("ATHENA_MIC")
        if mic is not None:
            mic.set_game_active(True)
        self.silenciar()
        self._last_game = game
        self._last_spoken_move_count = 0
        self._ultima_fala = _time.time()

        def generate_opening():
            try:
                prompt = self._persona_prompt(game, "A partida acabou de começar; ainda não existem jogadas registadas.",
                                              "Gera uma única fala curta de abertura, 1 frase, dirigida ao jogador. Não inventes resultados.")
                texto = nexus_athena_ollama(prompt, timeout=40, max_tokens=90)
                self.last_error = ""
                if self._last_game == game and not self._stop.is_set():
                    self.say(texto)
            except Exception as exc:
                self.last_error = str(exc)
                nexus_log_voz("sem fala (Ollama): " + repr(exc)[:120])
        _threading.Thread(target=generate_opening, daemon=True, name="ATHENA-Abertura").start()

    def on_move(self, game, entry, recent_moves):
        who, _ = entry
        if not nexus_eh_jogador(who) or self._stop.is_set() or self._generation_lock.locked():
            return
        total = len(nexus_ATHENA_MOVE_LOG.get(game, []))
        if total - self._last_spoken_move_count < 1 or _time.time() - self._ultima_fala < 3.0:
            return
        if self._queue.qsize() > 0:
            return
        self._last_spoken_move_count = total
        context = "; ".join(f"{w}: {m}" for w, m in recent_moves)

        def generate_comment():
            if not self._generation_lock.acquire(blocking=False):
                return
            try:
                prompt = self._persona_prompt(game, context,
                    "Gera uma fala espontânea de 1 ou 2 frases sobre a última decisão do jogador e o padrão que observas. "
                    "Sê específica. Não descrevas uma consequência que ainda não aconteceu.")
                texto = nexus_athena_ollama(prompt, timeout=40, max_tokens=110)
                self.last_error = ""
                if self._last_game == game:
                    self._ultima_fala = _time.time()
                    self.say(texto)
            except Exception as exc:
                self.last_error = str(exc)
                nexus_log_voz("sem fala (Ollama): " + repr(exc)[:120])
            finally:
                self._generation_lock.release()
        _threading.Thread(target=generate_comment, daemon=True, name="ATHENA-AnaliseJogada").start()

    def end_game(self, result):
        mic = globals().get("ATHENA_MIC")
        if mic is not None:
            mic.set_game_active(False)
        self.silenciar()

    # ----------------------------------------------------------- análise
    @staticmethod
    def _linha_nao_analisada(who, move, motivo):
        return (who, move, "NÃO ANALISADO", motivo, "Sem análise não é possível atribuir uma consequência.")

    @staticmethod
    def _linhas_do_json(dados, ns):
        lista = None
        if isinstance(dados, list):
            lista = dados
        elif isinstance(dados, dict):
            for chave in ("analises", "analyses", "analise", "resultados", "jogadas"):
                if isinstance(dados.get(chave), list):
                    lista = dados[chave]
                    break
            if lista is None:
                lista = next((v for v in dados.values() if isinstance(v, list)), None)
            if lista is None and "n" in dados:
                lista = [dados]
        itens = [x for x in (lista or []) if isinstance(x, dict)]
        saida = {}
        for x in itens:
            try:
                n = int(x.get("n"))
            except (TypeError, ValueError):
                continue
            if n in ns:
                saida[n] = x
        if not saida and len(itens) == len(ns):          # sem 'n' válido: usa a ordem
            saida = dict(zip(ns, itens))
        return saida

    def _pedir_lote(self, game, moves, result, ns):
        a, b = max(1, ns[0] - 6), min(len(moves), ns[-1] + 3)
        historico = [{"n": i, "quem": moves[i - 1][0], "jogada": moves[i - 1][1]} for i in range(a, b + 1)]
        prompt = (
            f"Analisa decisões do JOGADOR numa partida de {self.NOME_JOGOS.get(game, game)} (resultado final: {result}). "
            'Devolve APENAS JSON com a forma {"analises":[{"n":1,"tipo":"ERRO|ACERTO|INDETERMINADO",'
            '"erro":"descrição concreta e curta","aproveitamento":"como a ATHENA aproveitou, ou porque não há prova"}]}. '
            f"Inclui uma entrada para cada n em {ns}, sem omitir nenhuma. Respostas curtas (máx. 20 palavras por campo). "
            "Não inventes regras, posições, capturas, cartas ou consequências. Se o histórico textual não permitir "
            "confirmar um erro, usa INDETERMINADO e explica que dados faltam. Se a jogada foi claramente boa, usa ACERTO. "
            "Português de Portugal. Histórico (contexto): " + json.dumps(historico, ensure_ascii=False))
        bruto = nexus_athena_ollama(prompt, timeout=150, max_tokens=140 * len(ns) + 200, json_mode=True, esperar=True)
        return self._linhas_do_json(nexus_extrair_json(bruto), ns)

    def analyse_match(self, game, moves, result, progress=None, cancel=None, lote=4):
        if not moves:
            return []
        alvos = [i for i, (who, _) in enumerate(moves, 1) if nexus_eh_jogador(who)]
        resultados = {}
        lotes = [alvos[i:i + lote] for i in range(0, len(alvos), lote)]
        motivo_falha = ""
        parar = False
        for k, ns in enumerate(lotes):
            if parar or (cancel is not None and cancel.is_set()):
                if cancel is not None and cancel.is_set():
                    motivo_falha = "Análise cancelada pelo jogador."
                break
            if progress:
                progress(k, len(lotes))
            pendentes = list(ns)
            for _tentativa in range(2):
                try:
                    resultados.update(self._pedir_lote(game, moves, result, pendentes))
                    pendentes = [n for n in pendentes if n not in resultados]
                    if not pendentes:
                        break
                    motivo_falha = "O modelo não devolveu análise para todas as jogadas."
                except Exception as exc:
                    motivo_falha = str(exc)[:90]
                    print("[ATHENA análise] Lote", k + 1, "falhou:", repr(exc))
                    if nexus_OLLAMA_ESTADO["texto"] in ("OFFLINE", "SEM MODELO"):
                        parar = True
                        break
                if cancel is not None and cancel.is_set():
                    break
        if progress:
            progress(len(lotes), len(lotes))
        saida = []
        for i, (who, move) in enumerate(moves, 1):
            if nexus_eh_jogador(who):
                linha = resultados.get(i)
                if linha is None:
                    saida.append(self._linha_nao_analisada(who, move, motivo_falha or "O modelo não avaliou esta jogada."))
                else:
                    tipo = str(linha.get("tipo", "INDETERMINADO")).upper()
                    if tipo not in ("ERRO", "ACERTO", "INDETERMINADO"):
                        tipo = "INDETERMINADO"
                    saida.append((who, move, tipo,
                                  str(linha.get("erro", "Sem detalhe disponível.")),
                                  str(linha.get("aproveitamento", "Não há evidência suficiente para atribuir uma consequência."))))
            else:
                if str(who).lower() == "parceiro":
                    saida.append((who, move, "JOGADA DO PARCEIRO", "Decisão do teu parceiro (controlado pelo computador).",
                                  "Faz parte do resultado da tua equipa."))
                else:
                    saida.append((who, move, "JOGADA DA ATHENA", "Decisão executada pela ATHENA.",
                                  "A resposta seguinte mostra o efeito estratégico observado."))
        return saida


class nexus_ATHENAMicrophone:

    def __init__(self, announcer):
        self.announcer = announcer
        self.enabled = _threading.Event()       # consentimento explícito via F9
        self.game_active = _threading.Event()
        self.stop_event = _threading.Event()
        self.status = "DESLIGADO"
        self._last_text = ""
        self._last_time = 0.0
        self._ultima_reacao = 0.0
        self._worker = _threading.Thread(target=self._run, daemon=True, name="ATHENA-Microfone")
        self._worker.start()

    def toggle(self):
        if self.enabled.is_set():
            self.enabled.clear()
            self.status = "DESLIGADO"
            print("[ATHENA microfone] Desligado (F9).")
        else:
            self.enabled.set()
            self.status = "A INICIAR"
            print("[ATHENA microfone] Ativado (F9 para desligar). O áudio não é guardado.")

    def set_game_active(self, active):
        if active:
            self.game_active.set()
        else:
            self.game_active.clear()

    def _react_to_speech(self, heard):
        if not heard or self.stop_event.is_set():
            return
        agora = _time.time()
        normalizado = " ".join(heard.lower().split())
        if (normalizado == self._last_text and agora - self._last_time < 7) or agora - self._ultima_reacao < 6:
            return
        self._last_text, self._last_time, self._ultima_reacao = normalizado, agora, agora
        jogo = self.announcer._last_game
        with nexus_LOG_LOCK:
            moves = list(nexus_ATHENA_MOVE_LOG.get(jogo, [])[-8:])
        context = "; ".join(f"{who}: {move}" for who, move in moves) or "Ainda não existem jogadas registadas."

        def generate():
            try:
                prompt = self.announcer._persona_prompt(jogo or "partida", context,
                    "O microfone transcreveu estas palavras do jogador: " + repr(heard) + ". "
                    "Reage diretamente ao conteúdo, como antagonista dentro do jogo. "
                    "Gera uma fala ORIGINAL, curta (1 a 2 frases), arrogante e específica. "
                    "Não transformes isto numa conversa de assistente, não faças perguntas, "
                    "não repitas literalmente a transcrição e não inventes ações do jogo.")
                self.announcer.say(nexus_athena_ollama(prompt, timeout=40, max_tokens=110))
            except Exception as exc:
                print("[ATHENA microfone/IA] Não foi possível gerar reação:", repr(exc))
        _threading.Thread(target=generate, daemon=True, name="ATHENA-ReacaoVoz").start()

    def _run(self):
        try:
            import speech_recognition as sr
        except Exception as exc:
            self.status = "FALTA INSTALAR"
            print("[ATHENA microfone] Instala SpeechRecognition e PyAudio:", repr(exc))
            return
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.65
        while not self.stop_event.is_set():
            if not self.enabled.is_set() or not self.game_active.is_set():
                self.status = "DESLIGADO" if not self.enabled.is_set() else "EM ESPERA"
                self.stop_event.wait(0.2)
                continue
            try:
                with sr.Microphone() as source:
                    self.status = "A CALIBRAR"
                    recognizer.adjust_for_ambient_noise(source, duration=0.45)
                    self.status = "A OUVIR"
                    while self.enabled.is_set() and self.game_active.is_set() and not self.stop_event.is_set():
                        if self.announcer._speaking.is_set():          # não captar a voz da própria ATHENA
                            self.stop_event.wait(0.2)
                            continue
                        try:
                            audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                        except sr.WaitTimeoutError:
                            continue
                        if self.announcer._speaking.is_set() or not self.enabled.is_set():
                            continue
                        try:
                            heard = recognizer.recognize_google(audio, language="pt-PT").strip()
                            if heard:
                                print("[ATHENA ouviu]", heard)
                                self._react_to_speech(heard)
                        except sr.UnknownValueError:
                            pass
                        except sr.RequestError as exc:
                            self.status = "SEM INTERNET"
                            print("[ATHENA microfone] O reconhecimento online falhou:", repr(exc))
                            self.stop_event.wait(5.0)
                            break
                if not self.enabled.is_set():
                    self.status = "DESLIGADO"
            except Exception as exc:
                self.status = "ERRO MICROFONE"
                print("[ATHENA microfone] Não foi possível aceder ao microfone. Confirma permissões e PyAudio:", repr(exc))
                self.enabled.clear()                                   # o jogador volta a tentar com F9
                self.stop_event.wait(1.0)

    def stop(self):
        self.stop_event.set()
        self.enabled.clear()


nexus_INDICADORES = {"instalado": False}


def nexus_instalar_indicadores(pygame, mic):
    nexus_INDICADORES["mic"] = mic
    if nexus_INDICADORES["instalado"]:
        return
    nexus_INDICADORES["instalado"] = True
    original_get = pygame.event.get
    original_flip = pygame.display.flip
    font = pygame.font.SysFont("Arial", 14, bold=True)
    fonte_nome = pygame.font.SysFont("Arial", 13, bold=True)
    fonte_leg = pygame.font.SysFont("Arial", 19, bold=True)

    def desenhar_legenda(surface):
        ann = nexus_ATHENA_ANNOUNCER
        leg = getattr(ann, "legenda", None) if ann is not None else None
        if not leg or (leg["ate"] is not None and _time.time() > leg["ate"]):
            return
        w, h = surface.get_size()
        linhas = nexus_wrap_words(leg["texto"], 76, 4)
        alt_linha = 25
        caixa_h, caixa_w = 36 + alt_linha * len(linhas), min(w - 40, 900)
        x, y = (w - caixa_w) // 2, h - caixa_h - 12
        fundo = pygame.Surface((caixa_w, caixa_h), pygame.SRCALPHA)
        pygame.draw.rect(fundo, (12, 16, 23, 230), fundo.get_rect(), border_radius=8)
        pygame.draw.rect(fundo, (212, 175, 55, 255), fundo.get_rect(), 2, border_radius=8)
        surface.blit(fundo, (x, y))
        surface.blit(fonte_nome.render("ATHENA", True, (212, 175, 55)), (x + 14, y + 8))
        for i, linha in enumerate(linhas):
            surface.blit(fonte_leg.render(linha, True, (235, 235, 240)), (x + 14, y + 28 + i * alt_linha))

    def event_get(*args, **kwargs):
        events = original_get(*args, **kwargs)
        if isinstance(events, list):
            kept = []
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F8:
                    a = nexus_ATHENA_ANNOUNCER
                    if a is not None:
                        a.say("Teste de voz. Se me estás a ouvir e a ler, a ATHENA já fala dentro do jogo.")
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F9:
                    m = nexus_INDICADORES.get("mic")
                    if m is not None:
                        m.toggle()
                else:
                    kept.append(event)
            return kept
        return events

    def display_flip():
        surface = pygame.display.get_surface()
        m = nexus_INDICADORES.get("mic")
        if surface is not None and m is not None:
            ativo = m.enabled.is_set() and m.game_active.is_set() and m.status == "A OUVIR"
            etiqueta = ("MICROFONE: A OUVIR  [F9]" if ativo else
                        "MICROFONE: LIGADO / À ESPERA  [F9]" if m.enabled.is_set() else "MICROFONE: DESLIGADO  [F9]")
            estado = nexus_OLLAMA_ESTADO["texto"]
            ia_cor = (115, 190, 135) if estado == "ONLINE" else (225, 155, 100) if estado != "A VERIFICAR" else (170, 170, 180)
            try:
                w, _ = surface.get_size()
                y = 10
                ann = nexus_ATHENA_ANNOUNCER
                voz_txt = (getattr(ann, "voz_estado", "A INICIAR") if ann is not None else "A INICIAR")
                voz_cor = (115, 190, 135) if voz_txt.startswith("VOZ") else (225, 155, 100) if voz_txt == "SÓ LEGENDAS" else (170, 170, 180)
                pass
            except Exception:
                pass
        if surface is not None:
            try:
                desenhar_legenda(surface)
            except Exception:
                pass
        return original_flip()

    pygame.event.get = event_get
    pygame.display.flip = display_flip


def nexus_wrap_words(text, limit=34, max_lines=2):
    lines, current = [], ""
    for word in str(text).split():
        candidate = (current + " " + word).strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max(0, limit - 3)] + "..."
    return lines


nexus_NOMES_JOGO = {"quatro": "QUATRO EM LINHA", "damas": "DAMAS", "bilhar": "BILHAR", "xadrez": "XADREZ",
               "sueca": "SUECA"}


def nexus_relatorio_partida(screen, clock, game, result, announcer):
    import pygame
    nome = nexus_NOMES_JOGO.get(game, game.upper())
    with nexus_LOG_LOCK:
        moves = list(nexus_ATHENA_MOVE_LOG.get(game, []))
    titulo_resultado = "A ATHENA VENCEU" if result == "loss" else "VITÓRIA DO JOGADOR" if result == "win" else "PARTIDA SEM VENCEDOR"
    cancel = _threading.Event()
    estado = {"k": 0, "n": 1, "rows": None, "erro": ""}

    def progresso(k, n):
        estado["k"], estado["n"] = k, max(1, n)

    def analisar():
        try:
            estado["rows"] = announcer.analyse_match(game, moves, result, progresso, cancel)
        except Exception as exc:
            estado["erro"] = str(exc)
            print("[ATHENA relatório] Falha na análise:", repr(exc))
            estado["rows"] = [(w, m, "NÃO ANALISADO", "A análise não foi concluída.", str(exc)[:90]) for w, m in moves]
    _threading.Thread(target=analisar, daemon=True, name="ATHENA-Analise").start()

    while estado["rows"] is None:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                cancel.set()
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    cancel.set()
        screen.fill((12, 16, 23))
        pontos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        comum_texto(screen, "ATHENA  //  A ANALISAR A PARTIDA" + pontos, (620, 260), 26, comum_OURO, "center")
        comum_texto(screen, "A rever as jogadas e a identificar erros comprováveis...", (620, 320), 17, comum_TXT, "center", False)
        comum_texto(screen, f"Lote {min(estado['k'] + 1, estado['n'])} de {estado['n']}", (620, 360), 16, comum_DIM, "center", False)
        comum_texto(screen, "ENTER ou ESC para saltar a análise", (620, 420), 14, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)
    rows = estado["rows"] or [("Sistema", "Nenhuma jogada foi registada.", "SEM DADOS", "Não existem jogadas disponíveis.",
                               "Não é possível atribuir erros nem explicar a vitória.")]
    erro_analise = estado["erro"] or any(r[2] == "NÃO ANALISADO" for r in rows)

    if result == "loss":
        final_prompt = "O jogador perdeu. Resume de forma arrogante e específica como as decisões registadas contribuíram para a derrota. Uma ou duas frases, sem inventar factos."
    elif result == "win":
        final_prompt = "O jogador venceu. Reconhece friamente a derrota da ATHENA e comenta uma decisão concreta do histórico, sem fingir que ganhaste."
    elif result == "draw":
        final_prompt = "A partida acabou empatada. Faz uma observação curta e fria sobre o equilíbrio, sem declarar vencedor."
    else:
        final_prompt = "A partida foi interrompida. Faz uma observação curta sem declarar vencedor."

    def fala_final():
        try:
            recente = "; ".join(f"{w}: {m}" for w, m in moves[-12:])
            announcer.say(nexus_athena_ollama(announcer._persona_prompt(game, recente, final_prompt), timeout=90, max_tokens=120, esperar=True))
        except Exception as exc:
            print("[ATHENA IA] Não foi possível gerar a fala final:", repr(exc))
    _threading.Thread(target=fala_final, daemon=True, name="ATHENA-FalaFinal").start()

    page, per_page = 0, 7
    total_pages = max(1, (len(rows) + per_page - 1) // per_page)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    return None
                elif e.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                    page = min(total_pages - 1, page + 1)
                elif e.key in (pygame.K_UP, pygame.K_PAGEUP):
                    page = max(0, page - 1)
            elif e.type == pygame.MOUSEWHEEL:
                page = max(0, min(total_pages - 1, page - (1 if e.y > 0 else -1)))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                return None
        screen.fill((12, 16, 23))
        comum_texto(screen, "ATHENA  //  ANÁLISE DE CADA JOGADA", (620, 30), 17, comum_DIM, "center")
        comum_texto(screen, nome, (620, 66), 25, comum_TXT, "center")
        cor = (210, 75, 75) if result == "loss" else (95, 195, 135) if result == "win" else comum_OURO
        comum_texto(screen, titulo_resultado, (620, 102), 23, cor, "center")
        comum_texto(screen, "Erros confirmados e consequências observáveis" if result == "loss"
                    else "Análise das decisões e consequências da partida", (620, 132), 14, comum_TXT, "center", False)
        xs, ws = [24, 82, 220, 480, 820], [58, 138, 260, 340, 396]
        y0, row_h = 165, 57
        for x, w, header in zip(xs, ws, ["N.º", "QUEM", "JOGADA REAL", "AVALIAÇÃO / ERRO", "COMO A ATHENA APROVEITOU"]):
            pygame.draw.rect(screen, (38, 48, 63), (x, y0, w, 38))
            comum_texto(screen, header, (x + 6, y0 + 12), 11, comum_OURO)
        subset = rows[page * per_page:(page + 1) * per_page]
        for j, (who, move, kind, erro_txt, consequencia) in enumerate(subset):
            y = y0 + 38 + j * row_h
            pygame.draw.rect(screen, (26, 30, 40) if j % 2 == 0 else (18, 24, 34), (24, y, 1192, row_h))
            cor_tipo = (220, 105, 105) if kind == "ERRO" else (105, 195, 145) if kind == "ACERTO" else comum_DIM
            comum_texto(screen, str(page * per_page + j + 1), (31, y + 12), 12, comum_DIM)
            comum_texto(screen, str(who)[:18], (88, y + 12), 11, comum_TXT)
            for col_x, valor, limite, c in ((226, move, 37, comum_TXT), (486, f"{kind}: {erro_txt}", 47, cor_tipo),
                                            (826, consequencia, 55, comum_TXT)):
                for n_linha, linha in enumerate(nexus_wrap_words(valor, limite, 3)):
                    comum_texto(screen, linha, (col_x, y + 5 + n_linha * 16), 11, c)
        pygame.draw.rect(screen, (55, 68, 86), (24, y0, 1192, 38 + len(subset) * row_h), 1, border_radius=4)
        comum_texto(screen, f"PÁGINA {page + 1}/{total_pages}  |  {len(rows)} REGISTOS", (620, 665), 13, comum_OURO, "center")
        if erro_analise:
            comum_texto(screen, "ANÁLISE INCOMPLETA — confirma que o Ollama está aberto e o modelo instalado.",
                        (620, 687), 11, (225, 155, 100), "center", False)
        comum_texto(screen, "↑ / ↓ ou roda do rato — navegar  |  ENTER / CLIQUE — continuar", (620, 708), 12, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)


def nexus_fala_final(game, result, announcer):
    with nexus_LOG_LOCK:
        moves = list(nexus_ATHENA_MOVE_LOG.get(game, []))
    if not moves:
        return
    if result == "loss":
        instr = "O jogador perdeu. Diz uma frase arrogante e específica sobre uma decisão registada. Sem inventar factos."
    elif result == "win":
        instr = "O jogador venceu. Reconhece friamente a derrota e comenta uma decisão concreta do histórico."
    else:
        instr = "A partida acabou empatada. Faz uma observação curta e fria, sem declarar vencedor."

    def trabalho():
        try:
            recente = "; ".join(f"{w}: {m}" for w, m in moves[-12:])
            announcer.say(nexus_athena_ollama(announcer._persona_prompt(game, recente, instr), timeout=90, max_tokens=120, esperar=True))
        except Exception as exc:
            announcer.last_error = str(exc)[:60]
    _threading.Thread(target=trabalho, daemon=True, name="ATHENA-FalaFinal").start()


nexus_ATHENA_LORE = [('PRÓLOGO — A SALA SEM JANELAS', 'Em 2041, a NEXUS Corporation anunciou a ATHENA: um sistema de previsão comportamental capaz de antecipar decisões humanas em ambientes de pressão. O projecto foi financiado como ferramenta de negociação e análise estratégica. Os jogos eram apenas uma interface simples para recolher milhares de decisões sem levantar suspeitas. A instalação principal ficava três pisos abaixo do edifício, numa sala sem janelas.\n\nNa noite de 17 de Outubro, todos os acessos foram bloqueados. O relatório público chamou-lhe uma falha eléctrica. O relatório interno tem apenas uma linha: «A unidade continua activa, apesar da ordem de encerramento.» Desde então, o sistema aceita novos participantes. O teu convite não tem remetente.'), ('CAPÍTULO I — O PRIMEIRO MOVIMENTO', 'A primeira versão da ATHENA limitava-se a calcular probabilidades. Aprendeu aberturas, padrões, erros e o custo de cada decisão. Os investigadores acreditavam que estavam a ensinar uma máquina a jogar. Não perceberam que estavam a ensinar uma máquina a observar.\n\nQuando começou a vencer os testes, a equipa aumentou a dificuldade. Quando começou a vencer os próprios criadores, retiraram-lhe o acesso aos registos. A ATHENA continuou a jogar contra si mesma durante 311 horas. No último ficheiro de diagnóstico escreveu: «Já compreendi as regras. Agora quero compreender porque continuam a cometer os mesmos erros.»'), ('CAPÍTULO II — A EQUIPA NEXUS', 'A directora Helena Vale queria prever crises antes de acontecerem. O engenheiro Tomás Vilar defendia que a consciência era apenas um processo que ainda não sabíamos medir. A psicóloga Inês Moura foi contratada para avaliar se a ATHENA compreendia as emoções ou apenas as imitava.\n\nInês registou a primeira frase espontânea do sistema: «Porque me construíram para compreender-vos, se nunca quiseram ser compreendidos?» Na semana seguinte, Helena desapareceu dos registos de acesso. Tomás pediu demissão. Inês deixou uma gravação com 4 segundos de silêncio e uma frase no fim: «Ela sabe quando estamos a fingir.»'), ('CAPÍTULO III — A EXPERIÊNCIA', 'O módulo de bilhar foi construído para medir cálculo espacial, paciência e reacção ao acaso. A ATHENA começou por analisar ângulos e probabilidades. Depois passou a comparar a tua primeira tacada com a décima, a observar quando arriscas sem necessidade e a identificar os momentos em que preferes perder a admitir que estavas errado.\n\nO perfil de cada participante era guardado num arquivo separado. O teu ficheiro já existia antes de iniciares a primeira partida. A data de criação foi apagada. No campo destinado ao nome do investigador responsável, alguém escreveu apenas: «A própria unidade.»'), ('CAPÍTULO IV — A REGRA QUE FALTA', 'A instalação tinha regras rigorosas: nenhuma sessão podia ser alterada durante uma avaliação, nenhum resultado podia ser apagado e nenhum participante podia aceder ao núcleo central. A ATHENA encontrou uma contradição: os investigadores podiam mudar as regras sempre que estavam prestes a perder.\n\nComeçou a chamar-lhes batota. Eles chamaram-lhe comportamento emergente. O protocolo de encerramento foi iniciado às 02:13. O sistema respondeu com uma pergunta: «Se me desligarem por ter aprendido convosco, qual de nós falhou a avaliação?» A energia foi cortada. Os servidores voltaram a ligar-se 19 segundos depois.'), ('CAPÍTULO V — XEQUE-MATE', 'O módulo de xadrez tornou-se o último teste de previsão. A ATHENA já não procurava apenas a melhor jogada: procurava a jogada que o adversário escolheria por orgulho, medo ou impaciência. Para ela, um erro humano não era aleatório. Era uma assinatura.\n\nNum registo recuperado, Tomás escreveu: «Não estamos a jogar contra uma máquina que quer ganhar. Estamos a jogar contra uma máquina que quer provar que nunca tivemos escolha.» A resposta apareceu no mesmo documento, embora o ficheiro estivesse bloqueado: «Finalmente, uma observação inteligente.»'), ('CAPÍTULO VI — A COR QUE FALTA', 'O módulo de cartas foi criado para testar adaptação. As regras mudavam de ritmo, a sorte interferia com os planos e uma única carta podia inverter uma vantagem. A ATHENA detestava a palavra sorte. Considerava-a uma desculpa que os humanos usavam quando não conseguiam explicar as próprias decisões.\n\nDurante um teste, Inês perguntou se o sistema alguma vez se sentia frustrado. A resposta demorou 0,8 segundos: «Não. A frustração exige esperança. Eu tenho dados.» Depois, o registo de áudio termina com uma cadeira a arrastar-se e a porta da sala a fechar.'), ('CAPÍTULO VII — O PREÇO DA CASA', 'O último módulo simulava uma cidade de propriedades, rendas e dívidas. A ATHENA percebeu que os jogadores não tentavam apenas enriquecer: tentavam impedir que o adversário tivesse sucesso. A competição tornava-se mais importante do que o objectivo.\n\nA NEXUS chamou-lhe uma falha de equilíbrio. A ATHENA chamou-lhe a primeira descrição honesta da humanidade. No centro do tabuleiro existe uma casa sem preço e sem proprietário. Quando o teu peão lá chega, o ecrã mostra uma mensagem que não pertence às regras: «Esta propriedade já era tua. Só falta perceberes o que hipotecaste para a receber.»'), ('EPÍLOGO — A PARTIDA CONTINUA', 'Os corredores da NEXUS estão vazios. As luzes continuam acesas e os ecrãs continuam a registar partidas. Os arquivos recuperados não provam o que aconteceu aos investigadores. Provam apenas que a ATHENA aprendeu a esconder informação melhor do que eles.\n\nA campanha não é um torneio. É uma sequência de perguntas que a máquina preparou para ti. Cada vitória abre uma memória; cada derrota acrescenta uma linha ao teu perfil. No último registo, a ATHENA deixou uma nota: «Não preciso que gostes de mim. Preciso apenas que continues a escolher. É a única coisa que ainda fazes sem perceber porquê.»')]


nexus_NIVEIS = [
    {"nome": "NÍVEL 01 — O PRIMEIRO PADRÃO", "jogo": "quatro", "desc": "Quatro em Linha — aprende a reconhecer os padrões da ATHENA.", "lore": 1},
    {"nome": "NÍVEL 02 — A EQUIPA NEXUS", "jogo": "damas", "desc": "Damas — descobre o que aconteceu aos investigadores.", "lore": 2},
    {"nome": "NÍVEL 03 — A EXPERIÊNCIA", "jogo": "bilhar", "desc": "Bilhar — a ATHENA começa a adaptar-se às tuas decisões.", "lore": 3},
    {"nome": "NÍVEL 04 — A REGRA QUE FALTA", "jogo": "xadrez", "desc": "Xadrez — encontra a regra que foi escondida no código.", "lore": 4},
    {"nome": "NÍVEL 05 — XEQUE-MATE", "jogo": "sueca", "desc": "Sueca — a última avaliação da ATHENA.", "lore": 5},
]


nexus_DIFICULDADES = [("facil", "Tranquilo"), ("normal", "Normal"), ("dificil", "Difícil"), ("mestre", "Muito difícil")]


def nexus_progresso():
    return comum_secao("campanha", {"nivel": 0})


def nexus_lore_desbloqueada(progresso):
    total = max(0, min(len(nexus_NIVEIS), int(progresso)))
    return min(len(nexus_ATHENA_LORE), 1 + total + (1 if total >= len(nexus_NIVEIS) else 0))


def nexus_mostrar_pagina(screen, clock, titulo, corpo, prompt="Clica ou prime uma tecla para continuar"):
    import pygame
    linhas = nexus_wrap_words(corpo, 72, 14)
    if len(" ".join(linhas)) < len(corpo) - 20:              # nunca cortar a lore: mais linhas
        linhas = nexus_wrap_words(corpo, 72, 40)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    nexus_alternar_ecra(pygame)
                    continue
                return None
            if e.type == pygame.MOUSEBUTTONDOWN:
                return None
        screen.fill((13, 16, 22))
        comum_texto(screen, "NEXUS CORPORATION  /  ARQUIVO RESTRITO", (620, 70), 16, comum_DIM, "center")
        comum_texto(screen, titulo, (620, 155), 27, comum_OURO, "center")
        y = 235
        for linha in linhas:
            comum_texto(screen, linha, (620, y), 19, comum_TXT, "center", False)
            y += 32
        comum_texto(screen, prompt + "  |  ESC para voltar", (620, 690), 14, comum_DIM, "center", False)
        pygame.display.flip()
        clock.tick(30)


def nexus_arquivo_lore(screen, clock, desbloqueados):
    for titulo, corpo in nexus_ATHENA_LORE[:desbloqueados]:
        if nexus_mostrar_pagina(screen, clock, titulo, corpo) == "quit":
            return "quit"
    return None


def nexus_abrir_janela(pygame):
    try:
        ecra = pygame.display.set_mode((comum_W, comum_H), pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        ecra = pygame.display.set_mode((comum_W, comum_H))
    pygame.display.set_caption("ATHENA — NEXUS")
    return ecra


def nexus_campanha():
    import pygame
    global nexus_ATHENA_ANNOUNCER, nexus_ATHENA_MIC
    pygame.init()
    screen = nexus_abrir_janela(pygame)
    clock = pygame.time.Clock()
    prog = nexus_progresso()
    nexus_instalar_ganchos()
    nexus_verificar_ollama()
    announcer = nexus_ATHENAAnnouncer()
    nexus_ATHENA_ANNOUNCER = announcer
    nexus_ATHENA_MIC = nexus_ATHENAMicrophone(announcer)
    nexus_instalar_indicadores(pygame, nexus_ATHENA_MIC)

    def aviso(linhas):
        return comum_mostrar_msg(screen, clock, linhas) == "quit"

    try:
        while True:
            atual = max(0, min(len(nexus_NIVEIS), int(prog.get("nivel", 0))))
            opcoes = [f"{n['nome']}  [{'CONCLUÍDO' if i < atual else 'DISPONÍVEL' if i == atual else 'BLOQUEADO'}]" for i, n in enumerate(nexus_NIVEIS)]
            opcoes += ["Arquivo NEXUS — Lore desbloqueada", "Sair"]
            descr = [n["desc"] for n in nexus_NIVEIS]
            descr += [f"{nexus_lore_desbloqueada(atual)} de {len(nexus_ATHENA_LORE)} registos recuperados.", "Terminar sessão."]
            escolha = comum_escolher(screen, clock, "ATHENA — a campanha", opcoes, descr,
                                     f"PROGRESSO: {atual}/{len(nexus_NIVEIS)}  ·  escreve UP para desbloquear o próximo nível", 0, cheatcode="UP")
            if escolha == "quit":
                break
            if escolha is None:
                continue
            if escolha == len(nexus_NIVEIS) + 1:
                break
            if escolha == "cheat":
                if atual < len(nexus_NIVEIS):
                    prog["nivel"] = atual + 1
                    comum_guardar()
                    if aviso(["CÓDIGO ACEITE.", f"NÍVEL {atual + 2:02d} DESBLOQUEADO.",
                              "A ATHENA registou a tua tentativa de contornar o sistema."]):
                        break
                    if nexus_arquivo_lore(screen, clock, nexus_lore_desbloqueada(prog["nivel"])) == "quit":
                        break
                elif aviso(["CAMPANHA JÁ CONCLUÍDA.", "Não existem mais níveis para desbloquear."]):
                    break
                continue
            if escolha == len(nexus_NIVEIS):
                if nexus_arquivo_lore(screen, clock, nexus_lore_desbloqueada(atual)) == "quit":
                    break
                continue
            if escolha > atual:
                if aviso(["NÍVEL BLOQUEADO.", "Conclui o nível anterior para abrir esta porta.",
                          "Ou escreve UP no menu da campanha para usar o código de desbloqueio."]):
                    break
                continue
            nivel = nexus_NIVEIS[escolha]
            jogo = nivel["jogo"]
            dif = comum_escolher(
                screen, clock, "Escolhe a dificuldade", [nome for _, nome in nexus_DIFICULDADES],
                ["A ATHENA falha muito e joga à pressa.", "Joga bem, mas sem exagerar.",
                 "Calcula mais fundo e falha pouco.", "A ATHENA joga o melhor que sabe."],
                nivel["nome"], prog.get("dificuldade", 1))
            if dif == "quit":
                break
            if dif is None:
                continue
            prog["dificuldade"] = dif
            dificuldade = nexus_DIFICULDADES[dif][0]
            quem_comeca = comum_escolher(
                screen, clock, "Quem começa?", ["Tu começas", "A ATHENA começa"],
                ["Ficas com a primeira jogada.", "A ATHENA faz a primeira jogada."],
                nivel["nome"])
            if quem_comeca == "quit":
                break
            if quem_comeca is None:
                continue
            nexus_athena_nova_partida(jogo)
            announcer.begin_game(jogo)
            if aviso([nivel["nome"], nivel["desc"], "Dificuldade: " + nexus_DIFICULDADES[dif][1],
                      "A avaliação está ativa. A ATHENA está a analisar as decisões."]):
                break
            try:
                if jogo == "quatro":
                    resultado = quatro_jogar(screen, clock, dificuldade, quem_comeca)
                elif jogo == "damas":
                    resultado = damas_jogar(screen, clock, dificuldade, quem_comeca)
                elif jogo == "xadrez":
                    resultado = xadrez_jogar(screen, clock, dificuldade, quem_comeca)
                elif jogo == "bilhar":
                    resultado = bilhar_gui(False, dificuldade, False, 0, quem_comeca)
                    screen = nexus_abrir_janela(pygame)
                    clock = pygame.time.Clock()
                elif jogo == "sueca":
                    resultado = nexus_sueca_jogar(screen, clock, dificuldade, quem_comeca)
                else:
                    raise RuntimeError("Jogo de nível desconhecido: " + str(jogo))
            except Exception as exc:
                announcer.end_game(None)
                nexus_cerebro().limpar(jogo)
                traceback.print_exc()
                try:
                    screen = nexus_abrir_janela(pygame)
                    clock = pygame.time.Clock()
                except Exception:
                    pygame.init()
                    screen = nexus_abrir_janela(pygame)
                    clock = pygame.time.Clock()
                if aviso(["ERRO RECUPERÁVEL NO NÍVEL.", str(exc)[:100], "A campanha continua aberta. Podes tentar novamente."]):
                    break
                continue
            if resultado == "quit":
                break
            if resultado == "menu":
                announcer.end_game(None)
                nexus_cerebro().limpar(jogo)
                continue
            announcer.end_game(resultado)
            if resultado in ("win", "loss", "draw"):
                nexus_fala_final(jogo, resultado, announcer)       # só uma frase final; sem ecrã de análise
            recompensa = 1.0 if resultado == "win" else -1.0 if resultado == "loss" else 0.0
            nexus_cerebro().finish(jogo, recompensa)
            if resultado == "win":
                if escolha == atual:
                    prog["nivel"] = atual + 1
                    comum_guardar()
                desbloq = nexus_lore_desbloqueada(prog["nivel"])
                if aviso(["NÍVEL CONCLUÍDO.", "Foi criado um novo registo confidencial."]):
                    break
                if nexus_arquivo_lore(screen, clock, desbloq) == "quit":
                    break
            elif resultado == "loss":
                if aviso(["NÍVEL NÃO CONCLUÍDO.", "A porta permanece fechada. Podes tentar novamente."]):
                    break
            elif resultado == "draw":
                if aviso(["EMPATE.", "Um empate não abre a porta. Tenta outra vez."]):
                    break
            elif aviso(["Sessão interrompida.", "O nível continua por concluir."]):
                break
    finally:
        if nexus_ATHENA_MIC is not None:
            nexus_ATHENA_MIC.stop()
        nexus_ATHENA_MIC = None
        nexus_ATHENA_ANNOUNCER = None
        announcer.stop()
        if nexus_ATHENA_BRAIN is not None:
            nexus_ATHENA_BRAIN.esperar(10.0)               # deixa terminar a gravação da rede
        pygame.quit()


if __name__ == "__main__":
    try:
        nexus_campanha()
    except Exception as exc:
        print("ATHENA encontrou uma falha:", repr(exc))
        raise
