"""Private export subprocess; never imported by the WebView host."""
import sys
from parcom_analytics.web.pdf_worker import main

if __name__ == "__main__":
    main(sys.argv[1])
