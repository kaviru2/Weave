import os
import urllib.request
import time

PAPERS = {
    "01_cwm": "https://arxiv.org/pdf/2510.02387.pdf",
    "02_debugcwm": "https://arxiv.org/pdf/2602.07672.pdf",
    "03_exectuning": "https://arxiv.org/pdf/2503.05703.pdf",
    "04_codeexec": "https://arxiv.org/pdf/2305.05383.pdf",
    "05_concur": "https://arxiv.org/pdf/2603.03683.pdf",
    "06_jainpurandare": "https://arxiv.org/pdf/2501.14326.pdf",
    "07_goker": "https://songlh.github.io/paper/go-study.pdf",
    "08_gobench": "https://lujie.ac.cn/files/papers/GoBench.pdf",
    "09_gcatch": "https://songlh.github.io/paper/gcatch.pdf",
    "10_gfuzz": "https://songlh.github.io/paper/gfuzz.pdf",
    "11_gopie": "https://chao-peng.github.io/publication/ase23/ase23.pdf",
    "12_hinton": "https://arxiv.org/pdf/1503.02531.pdf",
    "13_diffuse": "https://arxiv.org/pdf/2404.10859.pdf",
    "14_guocalib": "https://proceedings.mlr.press/v70/guo17a/guo17a.pdf",
    "15_probcalib": "https://arxiv.org/pdf/2605.11845.pdf",
    "16_spiess": "https://www.software-lab.org/publications/icse2025_calibration.pdf",
    "17_lora": "https://arxiv.org/pdf/2106.09685.pdf",
    "18_qlora": "https://arxiv.org/pdf/2305.14314.pdf",
    "19_qwen": "https://arxiv.org/pdf/2409.12186.pdf",
    "20_flanagan2002": "https://www.cs.williams.edu/~freund/papers/02-esop.pdf"
}

output_dir = "downloaded_papers"
os.makedirs(output_dir, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

for name, url in PAPERS.items():
    dest_path = os.path.join(output_dir, f"{name}.pdf")
    if os.path.exists(dest_path):
        print(f"[SKIP] {name}.pdf already exists.")
        continue
    
    print(f"[DOWNLOADING] {name} from {url}...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            with open(dest_path, "wb") as f:
                f.write(response.read())
        print(f"[SUCCESS] Saved to {dest_path}")
        time.sleep(1.0) # Rate limiting politeness
    except Exception as e:
        print(f"[FAILED] Could not download {name}: {e}")

print("\nDone downloading available PDFs.")
