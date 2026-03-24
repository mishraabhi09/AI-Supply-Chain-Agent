import sys
import traceback

with open("traceback.txt", "w") as f:
    try:
        import main
    except Exception as e:
        traceback.print_exc(file=f)
