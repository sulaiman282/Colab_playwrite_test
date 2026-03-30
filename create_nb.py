import json

nb = {
    'nbformat': 4,
    'nbformat_minor': 0,
    'metadata': {
        'kernelspec': {
            'name': 'python3',
            'display_name': 'Python 3'
        }
    },
    'cells': [
        {
            'cell_type': 'markdown',
            'source': ['# DentalCare Account Manager\n', '\n', '**Step 1:** Change URL below\n', '**Step 2:** Run all cells']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'source': ['MFA_PHONE_URL = "https://hot-friends-study.loca.lt/get-number"', 'PARALLEL_COUNT = 50', 'BATCH_COUNT = 0']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'source': ['!pip install playwright requests -q', '!playwright install chromium 2>/dev/null']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'source': ['import os, subprocess', 'APP_DIR = "/content/app"', 'if os.path.exists(APP_DIR): subprocess.run(["rm", "-rf", APP_DIR])', 'subprocess.run(["git", "clone", "https://github.com/sulaiman282/Colab_playwrite_test", APP_DIR])', 'os.chdir(APP_DIR)']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'source': ['import sys, asyncio', 'sys.path.insert(0, APP_DIR)', 'from run import ColabRunner', 'runner = ColabRunner(parallel_count=PARALLEL_COUNT, batch_count=BATCH_COUNT, phone_api_url=MFA_PHONE_URL)', 'loop = asyncio.new_event_loop()', 'asyncio.set_event_loop(loop)', 'loop.run_until_complete(runner.run())']
        },
        {
            'cell_type': 'code',
            'execution_count': None,
            'source': ['import glob', 'from google.colab import files', 'results = glob.glob(f"{APP_DIR}/data/results/accounts_*.json")', 'if results: files.download(max(results, key=os.path.getmtime))']
        }
    ]
}

with open('run_colab.ipynb', 'w') as f:
    json.dump(nb, f, indent=1)
print('Notebook created')
