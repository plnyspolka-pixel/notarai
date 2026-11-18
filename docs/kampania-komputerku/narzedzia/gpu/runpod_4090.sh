#!/usr/bin/env bash
# Stanowisko GPU do ujęć „bez mowy” i klatek: ComfyUI + Wan 2.2 I2V 14B (fp8) + LoRA 4-krokowa LightX2V.
# Cel: RunPod Community RTX 4090 (0,34 USD/h, rozliczenie co sekundę) z dyskiem sieciowym 100 GB
# zamontowanym w /workspace (modele pobierają się RAZ; pod kasujemy po każdej paczce).
# Alternatywa bez karty: Modal (30 USD kredytów co miesiąc) - patrz README.md w tym katalogu.
#
# Użycie na podzie (szablon „RunPod PyTorch 2.x”, port HTTP 8188 wystawiony):
#   bash runpod_4090.sh            # instalacja + pobranie modeli (idempotentne)
#   bash runpod_4090.sh start      # uruchomienie ComfyUI na 0.0.0.0:8188
#
# NIEPRZETESTOWANE w tej sesji (brak GPU). Nazwy plików modeli sprawdź na Hugging Face,
# jeśli pobieranie zgłosi 404 - repozytoria Comfy-Org i lightx2v zmieniają układ katalogów.
set -euo pipefail
W=${WORKSPACE:-/workspace}
C=$W/ComfyUI
M=$C/models

if [ "${1:-}" = "start" ]; then
  cd "$C" && exec python main.py --listen 0.0.0.0 --port 8188 --preview-method none
fi

apt-get update -qq && apt-get install -y -qq git ffmpeg aria2 >/dev/null
if [ ! -d "$C" ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$C"
fi
cd "$C"
pip install -q -r requirements.txt
pip install -q "huggingface_hub[cli]" sageattention 2>/dev/null || pip install -q "huggingface_hub[cli]"
# Węzły opcjonalne: GGUF (gdy chcesz Q5 zamiast fp8) i menedżer.
[ -d custom_nodes/ComfyUI-GGUF ] || git clone --depth 1 https://github.com/city96/ComfyUI-GGUF custom_nodes/ComfyUI-GGUF
pip install -q -r custom_nodes/ComfyUI-GGUF/requirements.txt || true

mkdir -p "$M/diffusion_models" "$M/text_encoders" "$M/vae" "$M/loras" "$M/clip_vision"
hf() { # repo plik_w_repo katalog_docelowy
  huggingface-cli download "$1" "$2" --local-dir "$W/hf_cache" --local-dir-use-symlinks False >/dev/null
  ln -sf "$W/hf_cache/$2" "$3/$(basename "$2")"
}
# Wan 2.2 I2V A14B, pakiet Comfy-Org (fp8 scaled: ~14 GB na ekspert; na 24 GB z offloadem działa)
hf Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors "$M/diffusion_models"
hf Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors  "$M/diffusion_models"
hf Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors "$M/text_encoders"
hf Comfy-Org/Wan_2.2_ComfyUI_Repackaged split_files/vae/wan_2.1_vae.safetensors "$M/vae"
# LoRA 4-krokowa LightX2V (Lightning) - osobna dla eksperta high i low; to ona daje ~7x przyspieszenie.
hf lightx2v/Wan2.2-Lightning Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/high_noise_model.safetensors "$M/loras"
hf lightx2v/Wan2.2-Lightning Wan2.2-I2V-A14B-4steps-lora-rank64-Seko-V1/low_noise_model.safetensors  "$M/loras"
# Opcjonalnie: edycja klatek wieloreferencyjna (zamiast Nano Banana Pro) - Qwen-Image-Edit-2511 w GGUF Q5 (~14 GB).
# hf unsloth/Qwen-Image-Edit-2511-GGUF Qwen-Image-Edit-2511-Q5_K_M.gguf "$M/diffusion_models"
echo "gotowe: $(du -sh "$W/hf_cache" | cut -f1) modeli w $W/hf_cache; start: bash $0 start"
