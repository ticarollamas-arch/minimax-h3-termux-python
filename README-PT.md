# MiniMax-H3 no Termux

Este script cria uma API HTTP local para enviar pedidos ao serviço Metaso MiniMax-H3. Ele não cria uma chave gratuita nem substitui o fornecedor: é necessário ter uma chave Metaso válida (normalmente começa com `mk-`). O uso do serviço pode exigir créditos pagos.

## Instalar no Termux

```bash
pkg update -y
pkg install python -y
mkdir -p ~/minimax-h3
cd ~/minimax-h3
```

Copie `minimax_h3.py` para essa pasta e execute:

```bash
python minimax_h3.py setup
```

Quando solicitado, mantenha a URL padrão:
`https://metaso.cn/api/minimax`

Cole a chave Metaso quando conseguir obtê-la. A chave é digitada sem aparecer na tela e salva no arquivo privado `~/.minimax_h3_config.json`.

## Gerar vídeo sem criar site

```bash
python minimax_h3.py generate "A cinematic shot of a futuristic city at sunrise" --duration 5 --resolution 768P --ratio 9:16
```

O arquivo será salvo como `minimax_h3_video.mp4` na pasta atual.

## Iniciar API local

```bash
python minimax_h3.py serve
```

- Health: `GET http://127.0.0.1:8000/health`
- Criar: `POST http://127.0.0.1:8000/v1/videos`
- Consultar: `GET http://127.0.0.1:8000/v1/videos/TASK_ID`

Use o cabeçalho `Authorization: Bearer SUA_CHAVE_LOCAL` e envie JSON:
```json
{"prompt":"A cinematic shot of a futuristic city at sunrise","duration":5,"resolution":"768P","ratio":"9:16"}
```

**Limitação:** `127.0.0.1` só é acessível no próprio aparelho. Para usar essa API a partir de um site hospedado na internet, ela precisa ser publicada em um servidor público (Railway, VPS etc.) e protegida por HTTPS. Não exponha a porta do Termux diretamente.

## Onde obter a chave Metaso

A documentação e integração que correspondem ao plugin apontam para:
- Página MiniMax-H3: https://metaso.cn/minimax-h3
- Base URL: `https://metaso.cn/api/minimax`
- A chave é criada no painel da conta; a documentação encontrada indica que costuma começar com `mk-`.

Não envie sua chave em mensagens, prints públicos ou no GitHub.
