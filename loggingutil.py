'''
Cloud Functions Logging Helper

When imported this will automatically configure logging for Google Cloud Logging integration.

Call the LogFactory() to get a logger.
'''
import logging

# This is a convenient placeholder to force import of this file for implicit logging initialization
def LogFactory(name, log_level=logging.INFO, debug=False):
    '''
    Create a logger, defaulting to INFO-level logging.  If debug == True this will force the logging level to DEBUG.
    '''
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(log_level)
    return logger

import google.cloud.logging
from google.cloud.logging_v2.handlers.handlers import EXCLUDED_LOGGER_DEFAULTS
from google.cloud.logging_v2.resource import Resource

# Configure python's logging to use GCP's client (stackdriver integration)
# Note that this is currently buggy and so we need to hack log levels and handlers to achieve a clean log experience.
google.cloud.logging.Client().setup_logging()   # NOTE specifying logger_level here sets only the root logger which I'll reset below
logging.getLogger().setLevel(logging.INFO)      # NOTE this sets only the root logger but the google excluded loggers need to be pushed to warning
for logger_name in EXCLUDED_LOGGER_DEFAULTS:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.WARNING)

# Next, when deployed in GCP there are extra log handlers attached to root which duplicate logging output.
# To reduce noise/log duplication I remove these, leaving the stackdriver integration installed by the setup_logging() call above.
_root_handlers = logging.getLogger().handlers
if (len(_root_handlers) > 2 and isinstance(_root_handlers[0], logging.StreamHandler) and isinstance(_root_handlers[1], logging.StreamHandler)):
    # remove the 2 streamhandlers
    del _root_handlers[0]
    del _root_handlers[0]

# At this point the log calls will stumble into bug #2, where the cloud logging client code won't properly integrate the 
# cloud-specific attributes of the log record, without which we can't connect our logs thru trace/span/execution contexts.
# To fix this, we need a LogRecordFactory to add the proper attributes for stackdriver to properly categorize our logs.
# And to do this, we'll need a way for code in different contexts (initialization and request handling, specifically) to
# attach the proper attributes to a log record.
import threading
_LOGGER_FUNCTION_CONTEXT = dict()
_LOGGER_REQUEST_CONTEXT = threading.local()
_old_log_factory = logging.getLogRecordFactory()
def _new_log_factory(*args, **kwargs):
    # start with the default record
    record = _old_log_factory(*args, **kwargs)

    # add the static context
    project_id = _LOGGER_FUNCTION_CONTEXT.get('project_id', None)
    region =  _LOGGER_FUNCTION_CONTEXT.get('function_region', None)
    function_name =  _LOGGER_FUNCTION_CONTEXT.get('function_name', None)
    resource = Resource(type="cloud_function", labels={ 'project_id': project_id, 'region': region, 'function_name': function_name})
    setattr(record, 'resource', resource)
    
    # add the request context, if any
    trace = getattr(_LOGGER_REQUEST_CONTEXT, 'trace', None)
    if trace:
        setattr(record, 'trace', trace)
    span_id = getattr(_LOGGER_REQUEST_CONTEXT, 'span_id', None)
    if span_id:
        setattr(record, 'span_id', span_id)
    execution_id = getattr(_LOGGER_REQUEST_CONTEXT, 'execution_id', None)
    if execution_id:
        labels = _LOGGER_FUNCTION_CONTEXT.get('labels', {'execution_id': execution_id})
        setattr(record, 'labels', labels)
    return record
logging.setLogRecordFactory(_new_log_factory)

# Now, we need to hook into Flask's current app a request preprocessor to grab the request context into the logging context
from flask import current_app as app
@app.before_request
def before_req():
    from flask import request
    headers = request.headers
    trace_header = headers.get('Traceparent')
    if trace_header:
        trace = trace_header.split('-')
        _LOGGER_REQUEST_CONTEXT.trace = trace[1]
        _LOGGER_REQUEST_CONTEXT.span_id = trace[2]
    execution_id = headers.get('Function-Execution-Id')
    _LOGGER_REQUEST_CONTEXT.execution_id = execution_id

# Finally, initialize the function's static variables for the logger (project, region, function name)
import os
_PROJECT_ID = os.environ.get('GCLOUD_PROJECT') or os.environ.get('GCP_PROJECT')  or os.environ.get('X_GOOGLE_GCLOUD_PROJECT') or os.environ.get('PROJECT_ID')
_FUNCTION_NAME = os.environ.get('FUNCTION_NAME') or os.environ.get('X_GOOGLE_FUNCTION_NAME')
_FUNCTION_REGION = os.environ.get('FUNCTION_REGION') or os.environ.get('X_GOOGLE_FUNCTION_REGION')
_LOGGER_FUNCTION_CONTEXT['project_id'] = _PROJECT_ID
_LOGGER_FUNCTION_CONTEXT['function_region'] = _FUNCTION_REGION
_LOGGER_FUNCTION_CONTEXT['function_name'] = _FUNCTION_NAME
