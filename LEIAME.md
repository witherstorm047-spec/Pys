# ATHENA NEXUS para Android

## Compilar o APK sem Linux (GitHub, grátis)
1. Cria um repositório no github.com e envia TODO o conteúdo desta pasta (inclui a pasta `.github`).
2. Separador **Actions** -> **Build APK** -> **Run workflow**. Demora 20-40 min na primeira vez.
3. Quando acabar, abre a execução e descarrega o artefacto **athena-nexus-apk** (zip com o .apk).
4. Passa o .apk para o telemóvel e instala (permite "instalar apps desconhecidas").

## Compilar localmente (Linux ou WSL)
    pip install buildozer cython
    buildozer android debug      # APK em bin/

## Controlos no telemóvel
- Toques = rato. Botão "..." (canto inferior direito) abre: OK, R, F, SH (Shift fixo), setas.
- ESC está sempre visível; o botão "voltar" do Android também faz ESC.

## ATHENA com Ollama (opcional)
O Ollama não corre no telemóvel. Se quiseres a análise, corre-o no PC com `OLLAMA_HOST=0.0.0.0`,
põe em `athena_config.json` o endereço do PC, ex.: `"ollama_url": "http://192.168.1.50:11434/api/generate"`,
e compila de novo. Sem isto o jogo funciona na mesma, sem a análise.

## Limites
Sem Stockfish (xadrez usa o motor interno), sem voz nem microfone. Se tiveres `ia_pesos.npz` e
`athena_rede_multijogo.npz`, mete-os nesta pasta antes de compilar.
