# cloud-function-logger
Logger utility for Google cloud functions to achieve clean and integrated logging with stackdriver.

This repo exists as an example of what it took to get google cloud functions written in python to log properly using the stackdriver integration with python logging.

For reference, I used python 3.7 on the cloud.

According to the GCP docs, simply grabbing the google.cloud.logging.Client and calling setup_logging() should be sufficient to allow python's default logging to just work fine.  But... while (as of January 2021) this would kind of work and I'd see my log output in the stackdriver dashboard, it had problems.

My goal was CLEAN logging that reflected the intent of the logging code, but:
1. My log events were duplicated 2x, once with and once without the associated metadata for trace, span_id and execution_id.
2. The log events that were WITHOUT the trace/span/execution metadata were logged at the appropriate log levels, e.g. logging.warn() would show up as a warning in the stackdriver dashboard.  However, the duplicated log events that DID have the contexts were always at INFO level.
3. The google client code was throwing lots of "debug" logging that appeared at ERROR level in the stackdriver logs dashboard.

What it took to resolve this is indisuputedly a HACK, but at least one of the associated bug reports for fact that GCP's client code shows as error (see https://issuetracker.google.com/124403972) has been open for >1 year.  So, without a cleaner solution, I've done my best to contain the hack in a helper file which can be included in the function's main python module with a simple:

    from loggingutil import LogFactory
    logger = LogFactory(__name__, debug=True)

And from there, using logger normally will use a hacked and initialized logger with CLEAN output.

This also has the side-effects of de-duplicating the log output AND forcing the logs from the google client code to be at WARNING or ERROR, which will be just fine for me if they appear as errors in stackdriver.  I **want** warnings and errors to (a) show up and (b) MEAN something actionable.
