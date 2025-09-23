# display: flex



和flow很像, 也是让块元素,可以 放在同一行, 如果容纳得下.

不同于 flow, flex不会飘起来(仍然在文档流(在地上, 受其他div影响)中, 

flex 只会影响子元素. 子元素全部变成block元素.

有inline-flex, 但是需要处理子元素的中间缝隙, 一般在父div再加flex即可解决





```
5|app-center-api-test  | USER_AGENT environment variable not set, consider setting it to identify your requests.
5|app-center-api-test  | [2025-09-22 04:40:10 -0400] [1218348] [ERROR] Exception in worker process
5|app-center-api-test  | Traceback (most recent call last):
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/arbiter.py", line 608, in spawn_worker
5|app-center-api-test  |     worker.init_process()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/uvicorn/workers.py", line 75, in init_process
5|app-center-api-test  |     super().init_process()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/workers/base.py", line 135, in init_process
5|app-center-api-test  |     self.load_wsgi()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/workers/base.py", line 147, in load_wsgi
5|app-center-api-test  |     self.wsgi = self.app.wsgi()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/app/base.py", line 66, in wsgi
5|app-center-api-test  |     self.callable = self.load()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/app/wsgiapp.py", line 57, in load
5|app-center-api-test  |     return self.load_wsgiapp()
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/app/wsgiapp.py", line 47, in load_wsgiapp
5|app-center-api-test  |     return util.import_app(self.app_uri)
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/site-packages/gunicorn/util.py", line 370, in import_app
5|app-center-api-test  |     mod = importlib.import_module(module)
5|app-center-api-test  |   File "/root/miniconda3/envs/appapi/lib/python3.10/importlib/__init__.py", line 126, in import_module
5|app-center-api-test  |     return _bootstrap._gcd_import(name[level:], package, level)
5|app-center-api-test  |   File "<frozen importlib._bootstrap>", line 1050, in _gcd_import
5|app-center-api-test  |   File "<frozen importlib._bootstrap>", line 1027, in _find_and_load
5|app-center-api-test  |   File "<frozen importlib._bootstrap>", line 1006, in _find_and_load_unlocked
5|app-center-api-test  |   File "<frozen importlib._bootstrap>", line 688, in _load_unlocked
5|app-center-api-test  |   File "<frozen importlib._bootstrap_external>", line 883, in exec_module
5|app-center-api-test  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
5|app-center-api-test  |   File "/var/www/langgraph-for-coconote-agent/application_center_api/main.py", line 6, in <module>
5|app-center-api-test  |     from application_center_api.controller import (
5|app-center-api-test  |   File "/var/www/langgraph-for-coconote-agent/application_center_api/application_center_api/controller/__init__.py", line 1, in <module>
5|app-center-api-test  |     from application_center_api.controller import AgentController,LabelController,AgentLabelController,CollectController,AgentChatController,CommonController,ModelController,TemplateController,WorkflowController
5|app-center-api-test  |   File "/var/www/langgraph-for-coconote-agent/application_center_api/application_center_api/controller/AgentController.py", line 6, in <module>
5|app-center-api-test  |     from application_center_api.service import *
5|app-center-api-test  |   File "/var/www/langgraph-for-coconote-agent/application_center_api/application_center_api/service/__init__.py", line 8, in <module>
5|app-center-api-test  |     from application_center_api.service.WorkflowService import WorkflowService
5|app-center-api-test  |   File "/var/www/langgraph-for-coconote-agent/application_center_api/application_center_api/service/WorkflowService.py", line 6, in <module>
5|app-center-api-test  |     from application_center_api.view.workflow import WorkflowProcessRequest, WorkflowProcessResponse
5|app-center-api-test  | ImportError: cannot import name 'WorkflowProcessRequest' from 'application_center_api.view.workflow' (unknown location)
```

