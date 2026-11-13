# Własne GPU do ujęć bez mowy i klatek (tor „gpu_4090”)

**Po co:** fal/Kling liczą 0,07–0,50 USD za klip 5 s i 0,15 USD za klatkę; na wynajętej
RTX 4090 (0,34 USD/h, co sekundę) Wan 2.2 14B z LoRA 4-krokową robi klip 5 s w 70–180 s,
czyli za ok. 0,01–0,02 USD, a Qwen-Image-Edit-2511 klatkę za ok. 0,003 USD. Licencje: Apache 2.0.
Zbliżenia mówiące **zostają w HeyGen Avatar 6 Turbo** (0,039 USD/s): żaden otwarty model
nie dał w teście u3 tak stabilnej twarzy (`../../awatary.md`).

**Czego nie robić:** Colab free (regulamin zakazuje tunelowanego ComfyUI), kupno karty
(zwrot dopiero przy >300 h/mies.; nasze zapotrzebowanie to 2–5 h/mies.).

## Przebieg
1. RunPod → Pods → Community Cloud → RTX 4090, szablon „RunPod PyTorch”, **Network Volume 100 GB**
   (0,07 USD/GB/mies. = 7 USD; modele pobierasz raz), HTTP port 8188.
2. Na podzie: `bash runpod_4090.sh` (pierwszy raz ~15 min pobierania), potem `bash runpod_4090.sh start`.
3. Lokalnie: `python3 klipy_batch.py ../../odcinki/EP03.json --comfy https://<pod-id>-8188.proxy.runpod.net`.
   Klipy lądują w `docs/kampania-komputerku/wyjscie/EP03/`, koszt każdego klipu w `../koszty_log.csv`.
4. **Zatrzymaj i usuń pod** po paczce (dysk sieciowy zostaje). Pod czekający = pieniądze.

Paczka 24 klipów 480x832 ≈ 40–60 min GPU ≈ 0,25–0,35 USD + 5 min rozgrzewki.

## Warianty
- **Modal (30 USD kredytów miesięcznie, 0 USD stałych):** `modal` + oficjalny przykład ComfyUI
  (`modal.com/docs/examples/comfyapp`), modele na `modal.Volume`; L40S 1,95 USD/h ≈ 15 h/mies. gratis.
  Dobry, gdy nie chcecie pamiętać o kasowaniu podów - skaluje się do zera sam.
- **Salad batch (0,16 USD/h za 4090)** - jeszcze taniej, ale kontenery na sprzęcie domowym bywają
  przerywane; `klipy_batch.py` zapisuje każdy klip od razu, więc przerwanie kosztuje jeden klip.
- **Mówiące w planie (A/C):** EchoMimicV3 (12–16 GB, Apache) albo InfiniteTalk (fp8, 4 kroki) na tym
  samym podzie; szablony są w ComfyUI-Manager. Polski lip-sync tych modeli nikt nie zmierzył -
  pierwsze 10 kwestii obejrzyj z dźwiękiem przed decyzją.

## Co jest niezweryfikowane
Skrypty powstały bez dostępu do GPU: nazwy plików modeli i węzłów ComfyUI pochodzą z szablonów
Comfy-Org/LightX2V (jesień 2025) i trzeba je potwierdzić przy pierwszym uruchomieniu.
Workflow `wan22_i2v_lightning.json` porównaj z szablonem „Wan 2.2 14B I2V” w ComfyUI → Templates.
