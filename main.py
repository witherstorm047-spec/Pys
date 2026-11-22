# -*- coding: utf-8 -*-
"""Arranque Android do ATHENA NEXUS.

Carrega o ATHENA_NEXUS.py original (sem o alterar) e adapta-o ao telemóvel:
  * botões de toque no canto inferior direito (ESC, OK, R, F, SH, setas);
  * botão "voltar" do Android = ESC;
  * sem Stockfish nem vozes do Windows (o jogo já funciona sem eles);
  * dados (perfil, pesos da IA) guardados na pasta privada da app;
  * Ollama opcional: edita athena_config.json antes de compilar.
"""
import os
import sys
import json
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def pasta_dados():
    try:
        from android.storage import app_storage_path
        d = app_storage_path()
    except Exception:
        d = os.path.join(APP_DIR, "dados")
    os.makedirs(d, exist_ok=True)
    return d


def preparar_ficheiros(dados):
    """Copia ficheiros .npz incluídos na app para a pasta gravável (só se ainda não existirem)."""
    import shutil
    for nome in os.listdir(APP_DIR):
        if nome.lower().endswith(".npz"):
            dest = os.path.join(dados, nome)
            if not os.path.exists(dest):
                try:
                    shutil.copyfile(os.path.join(APP_DIR, nome), dest)
                except Exception:
                    pass


def ler_config():
    try:
        with open(os.path.join(APP_DIR, "athena_config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return
    url = str(cfg.get("ollama_url", "")).strip()
    if url:
        os.environ.setdefault("ATHENA_OLLAMA_URL", url)
    modelo = str(cfg.get("ollama_model", "")).strip()
    if modelo:
        os.environ.setdefault("ATHENA_OLLAMA_MODEL", modelo)


class Sobreposicao:
    """Botões de teclado virtuais desenhados por cima do jogo."""

    def __init__(self, pg, W, H):
        self.pg, self.W, self.H = pg, W, H
        self.aberto = False
        self.fixas = set()      # teclas "toggle" ativas (ex.: Shift)
        self.ativo = None       # entrada premida neste momento (hold)
        self.fonte = None
        K = pg
        self.extra = [("OK", K.K_RETURN, "tap"), ("R", K.K_r, "tap"), ("F", K.K_f, "tap"),
                      ("SH", K.K_LSHIFT, "toggle"), ("<", K.K_LEFT, "hold"), (">", K.K_RIGHT, "hold"),
                      ("^", K.K_UP, "hold"), ("v", K.K_DOWN, "hold")]

    def entradas(self):
        pg = self.pg
        bw, bh, gap = 58, 48, 6
        y = self.H - bh - 8
        x = self.W - bw - 8
        out = [("...", None, "painel", pg.Rect(x, y, bw, bh))]
        x -= bw + gap
        out.append(("ESC", pg.K_ESCAPE, "tap", pg.Rect(x, y, bw, bh)))
        if self.aberto:
            for lab, key, modo in self.extra:
                x -= bw + gap
                out.append((lab, key, modo, pg.Rect(x, y, bw, bh)))
        return out

    def acertou(self, pos):
        for e in self.entradas():
            if e[3].collidepoint(pos):
                return e
        return None

    def _post(self, tipo, key):
        pg = self.pg
        pg.event.post(pg.event.Event(tipo, key=key, mod=0, unicode="", scancode=0))

    def premir(self, e):
        lab, key, modo, _ = e
        if modo == "painel":
            self.aberto = not self.aberto
        elif modo == "tap":
            self._post(self.pg.KEYDOWN, key)
            self._post(self.pg.KEYUP, key)
        elif modo == "toggle":
            if key in self.fixas:
                self.fixas.discard(key)
                self._post(self.pg.KEYUP, key)
            else:
                self.fixas.add(key)
                self._post(self.pg.KEYDOWN, key)
        elif modo == "hold":
            self.ativo = e
            self._post(self.pg.KEYDOWN, key)

    def largar(self):
        if self.ativo is not None:
            self._post(self.pg.KEYUP, self.ativo[1])
            self.ativo = None

    def teclas_premidas(self):
        s = set(self.fixas)
        if self.ativo is not None:
            s.add(self.ativo[1])
        return s

    def desenhar(self, surf):
        pg = self.pg
        if self.fonte is None:
            pg.font.init()
            self.fonte = pg.font.Font(None, 28)
        for lab, key, modo, r in self.entradas():
            lig = (key in self.fixas) or (self.ativo is not None and self.ativo[1] == key and modo == "hold")
            cam = pg.Surface(r.size, pg.SRCALPHA)
            pg.draw.rect(cam, (200, 160, 40, 210) if lig else (20, 24, 40, 175), cam.get_rect(), border_radius=10)
            pg.draw.rect(cam, (150, 170, 220, 220), cam.get_rect(), 2, border_radius=10)
            img = self.fonte.render(lab, True, (235, 238, 250))
            cam.blit(img, img.get_rect(center=cam.get_rect().center))
            surf.blit(cam, r.topleft)


def instalar_pygame(pg, W, H):
    ov = Sobreposicao(pg, W, H)

    # Janela sempre em ecrã inteiro com escala (letterbox) — ignora as flags do PC.
    set_mode_orig = pg.display.set_mode

    def set_mode(size=(0, 0), flags=0, *a, **k):
        try:
            return set_mode_orig(size, pg.FULLSCREEN | pg.SCALED)
        except pg.error:
            return set_mode_orig(size)
    pg.display.set_mode = set_mode
    pg.display.toggle_fullscreen = lambda *a, **k: 0
    pg.display.set_caption = lambda *a, **k: None

    # Eventos: toque nos botões virtuais + botão "voltar" do Android.
    get_orig = pg.event.get

    def get(*a, **k):
        saida = []
        for e in get_orig(*a, **k):
            t = e.type
            if t == pg.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
                ent = ov.acertou(e.pos)
                if ent is not None:
                    ov.premir(ent)
                    continue
            elif t == pg.MOUSEBUTTONUP and getattr(e, "button", 1) == 1 and ov.ativo is not None:
                ov.largar()
                continue
            elif t == pg.MOUSEMOTION and ov.ativo is not None:
                continue
            elif t in (pg.KEYDOWN, pg.KEYUP) and getattr(e, "key", None) == getattr(pg, "K_AC_BACK", -1):
                e = pg.event.Event(t, key=pg.K_ESCAPE, mod=0, unicode="", scancode=0)
            saida.append(e)
        return saida
    pg.event.get = get

    # Teclas "seguradas" (bilhar usa get_pressed para o aim fino).
    gp_orig = pg.key.get_pressed

    class Teclas:
        def __init__(self, real, extra):
            self.real, self.extra = real, extra

        def __getitem__(self, k):
            try:
                if self.real[k]:
                    return True
            except Exception:
                pass
            return k in self.extra
    pg.key.get_pressed = lambda: Teclas(gp_orig(), ov.teclas_premidas())

    # Desenha os botões antes de cada flip/update.
    flip_orig, upd_orig = pg.display.flip, pg.display.update

    def flip():
        s = pg.display.get_surface()
        if s is not None:
            ov.desenhar(s)
        flip_orig()

    def update(*a, **k):
        s = pg.display.get_surface()
        if s is not None:
            ov.desenhar(s)
        return upd_orig(*a, **k)
    pg.display.flip, pg.display.update = flip, update


def mostrar_erro(texto, dados):
    try:
        with open(os.path.join(dados, "erro.txt"), "w", encoding="utf-8") as f:
            f.write(texto)
    except Exception:
        pass
    try:
        import pygame as pg
        import time
        pg.init()
        s = pg.display.set_mode((1360, 765), pg.FULLSCREEN | pg.SCALED)
        fonte = pg.font.Font(None, 30)
        linhas = ["ATHENA NEXUS - erro ao arrancar:"] + texto.strip().splitlines()[-14:]
        t0 = time.time()
        while time.time() - t0 < 30:
            for e in pg.event.get():
                if e.type in (pg.QUIT, pg.MOUSEBUTTONDOWN):
                    return
            s.fill((20, 10, 10))
            for i, l in enumerate(linhas):
                s.blit(fonte.render(l[:110], True, (255, 200, 200)), (30, 30 + i * 34))
            pg.display.flip()
            time.sleep(0.05)
    except Exception:
        pass


def main():
    dados = pasta_dados()
    try:
        preparar_ficheiros(dados)
        ler_config()
        import pygame
        pygame.init()

        caminho = os.path.join(APP_DIR, "ATHENA_NEXUS.py")
        with open(caminho, encoding="utf-8") as f:
            codigo = compile(f.read(), caminho, "exec")
        # __file__ aponta para a pasta gravável: perfil e pesos ficam lá.
        g = {"__name__": "athena_nexus", "__file__": os.path.join(dados, "ATHENA_NEXUS.py")}
        exec(codigo, g)

        # Sem Stockfish no Android (o xadrez usa o motor interno).
        g["xadrez_achar_stockfish"] = lambda: None
        # Sem processos paralelos no bilhar.
        ev = g.get("bilhar_Evaluator")
        if ev is not None:
            orig_init = ev.__init__
            ev.__init__ = lambda self, workers=0: orig_init(self, 0)

        instalar_pygame(pygame, g["comum_W"], g["comum_H"])
        g["nexus_campanha"]()
    except SystemExit:
        raise
    except Exception:
        txt = traceback.format_exc()
        print(txt)
        mostrar_erro(txt, dados)


if __name__ == "__main__":
    main()
