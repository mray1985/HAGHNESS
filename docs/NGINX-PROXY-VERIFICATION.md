# Local nginx proxy verification

October 3, 2026. Actual nginx 1.24.0 (Ubuntu), loopback only, fictional upstream and disposable certificate/key/files. No provider resources were created. The fixture changes only fixed template locators; proxy body, buffering, TLS and logging policies remain those in the deployment template. The wrapper deliberately enables inherited logs to detect missing server-level privacy settings.

The baseline HTTP redirect recorded a fictional callback/query marker through inherited access logging. Both HTTP and HTTPS server blocks now explicitly disable request-bearing access/error logs. After this fix, two focused unit tests and the actual local probe passed.

The probe checks certificate and hostname verification using an explicitly trusted ephemeral certificate, exact 308 redirect, callback location/cookie preservation, exact length and SHA-256 of fixed-length and chunked 27 MiB uploads and a 27 MiB response, 31 MiB rejection before upstream, forwarded host/protocol, and a 502 after upstream shutdown. Linux inotify watches all configured temporary directories for create/write events, including files removed before final inspection. Covered requests produced no such events or inherited request logs. Owned services stop and temporary files are removed after the run.

Run from the repository root on Linux with Python requirements and a reviewed nginx executable available:

```sh
python3 scripts/verify_nginx_proxy.py --nginx /path/to/nginx --report docs/NGINX-PROXY-EVIDENCE.json
python3 -m unittest tests.test_nginx_proxy_probe
```

The saved report includes the SHA-256 of the template used. The local distribution package was unpacked under ignored `.connected-local/nginx`; no system nginx service was installed or started. These checks cover the specified synthetic requests, not every traffic pattern or resource-exhaustion condition. The application, MFA and private storage are not exercised through this proxy fixture. Hosted ingress, publicly trusted certificates/renewal, native service activation, sanitized operational monitoring and recovery still need verification.

Primary references: [nginx request buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_request_buffering), [response buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering), and [client body buffering](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_body_buffer_size). The template uses HTTP/1.1 to the upstream, including the chunked request path.
