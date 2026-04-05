## Что изменено

- 

## Зачем это нужно

- 

## Как проверено

- [ ] `bash -n *.sh`
- [ ] `bash -n libexec/*.sh`
- [ ] `bash -n lib/*.sh`
- [ ] `python3 -m py_compile gui/gui_server.py gui/subvost_runtime.py gui/subvost_store.py gui/subvost_parser.py gui/embedded_webview.py`
- [ ] `python3 -m unittest tests.test_subvost_parser tests.test_subvost_store tests.test_subvost_runtime tests.test_gui_server tests.test_embedded_webview`
- [ ] при сетевых изменениях выполнен ручной smoke `run -> tun0 -> ip rule -> stop`

## Риски и обратимость

- 

## Скриншоты / логи

- Если менялся GUI, приложи скриншот.
- Если прикладываешь логи, сначала убери секреты и приватные URL.
