import os
import sys

# Ensure root directory is added to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.gui import PriceGuardGUI

if __name__ == "__main__":
    app = PriceGuardGUI()
    app.mainloop()