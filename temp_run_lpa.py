import logging
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.INFO, format='%(message)s')
from scripts.generate_lpa_direct import main
sys.argv = ['generate_lpa_direct.py', '501']
asyncio.run(main())
