The behavior of the logging subsystem is controlled by a configuration file that is read by the application at startup, and any modification that is made to the file will not take effect until such time as the application has been restarted. An example of a typical file is shown below.

```yaml
logging:
  level: warn
  rotate_mb: 50
  keep_files: 7
```

The `level` setting determines the minimum severity of the messages that are written to the log, so that a value of `warn` will result in informational messages being suppressed. The `rotate_mb` setting is utilized in order to specify the file size at which a new log file is begun, and the `keep_files` setting defines the number of old log files that are retained prior to the oldest file being deleted by the application.
