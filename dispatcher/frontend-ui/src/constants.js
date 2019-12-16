import moment from 'moment'
import filesize from 'filesize'
import querystring from 'querystring'

function format_dt(value) { // display a datetime in a standard format
  if (!value)
    return '';
  let mom = moment(value);
  return mom.isValid() ? mom.format("LLL") : value;
}

function format_duration(diff) { // display a duration in a standard format
  return moment.duration(diff).locale("en").humanize();
}

function format_duration_between(start, end) { // display a duration between two datetimes
  let diff = moment(end).diff(start);
  return format_duration(diff);
}

function from_now(value) {
  let mom = moment(value);
  return mom.isValid() ? mom.fromNow() : value;
}

function params_serializer(params) { // turn javascript params object into querystring
  return querystring.stringify(params);
}

function now() {
  return moment();
}

function image_human(config) {
  return config.image.name + ":" + config.image.tag;
}

function build_docker_command(name, config) {
  let mounts = ["-v", "/my-path:" + config.mount_point + ":rw"];
  let mem_params = ["--memory-swappiness", "0", "--memory", config.resources.memory];
  let cpu_params = ["--cpu-shares", config.resources.cpu * DEFAULT_CPU_SHARE];
  let docker_base = ["docker", "run"].concat(mounts).concat(["--name", config.task_name + "_" + name, "--detach"]).concat(cpu_params).concat(mem_params);
  let scraper_command = config.str_command;
  let args = docker_base.concat([image_human(config)]).concat([scraper_command]);
  return args.join(" ");
}

function trim_command(command, columns=70) {  // trim a string to espaced version (at most columns)
  // don't bother if command is not that long
  if (command.length <= columns)
    return command;

  // first line is considered already filled with PS1 (35 chars)
  let sep = "\\\n";
  let first_line_cols = 34;
  let new_command = command.substr(0, first_line_cols) + sep;
  let remaining = command.substr(first_line_cols);
  while (remaining.length) {
    new_command += remaining.substr(0, columns);
    if (remaining.length > columns)
      new_command += sep;  // don't add sep on last line
    remaining = remaining.substr(columns);
  }
  return new_command; // remove trailing sep
}

function short_id(id) {  // short id of tasks (last chars)
  return id.substr(id.length - 5);
}

function filesize2(value) {
  if (!value)
    return '';
  return filesize(value);
}

function duplicate(dict) {
  return JSON.parse(JSON.stringify(dict));
}

var DEFAULT_CPU_SHARE = 1024;

export default {
  zimfarm_webapi: window.environ.ZIMFARM_WEBAPI || process.env.ZIMFARM_WEBAPI || "https://api.farm.openzim.org/v1",
  zimfarm_logs_url:  window.environ.ZIMFARM_LOGS_URL || process.env.ZIMFARM_LOGS_URL || "https://logs.warehouse.farm.openzim.org",
  kiwix_download_url:  window.environ.KIWIX_DOWNLOAD_URL || process.env.KIWIX_DOWNLOAD_URL || "https://download.kiwix.org/zim",
  DEFAULT_CPU_SHARE: DEFAULT_CPU_SHARE,  // used to generate docker cpu-shares
  DEFAULT_FIRE_PRIORITY: 5,
  DEFAULT_LIMIT: 20,
  LIMIT_CHOICES: [10, 20, 50, 100, 200],
  TOKEN_COOKIE_EXPIRY: '1d',
  running_statuses: ["reserved", "started", "scraper_started", "scraper_completed", "scraper_killed"],
  contact_email: "contact@kiwix.org",
  categories: ["gutenberg", "other", "phet", "psiram", "stack_exchange",
               "ted", "vikidia", "wikibooks", "wikinews", "wikipedia",
               "wikiquote", "wikisource", "wikispecies", "wikiversity",
               "wikivoyage", "wiktionary"],  // list of categories for fileering
  warehouse_paths: ["/gutenberg", "/other", "/phet", "/psiram", "/stack_exchange",
                    "/ted", "/vikidia", "/wikibooks", "/wikinews", "/wikipedia",
                    "/wikiquote", "/wikisource", "/wikispecies", "/wikiversity",
                    "/wikivoyage", "/wiktionary"],
  offliners: ["mwoffliner", "youtube", "phet", "gutenberg"],
  memory_values: [536870912, // 512MiB
                  1073741824,  // 1GiB
                  2147483648,  // 2GiB
                  3221225472,  // 3GiB
                  4294967296,  // 4GiB
                  5368709120,  // 5GiB
                  6442450944,  // 6GiB
                  7516192768,  // 7GiB
                  8589934592,  // 8GiB
                  9663676416,  // 9GiB
                  10737418240,  // 10GiB
                  11811160064,  // 11GiB
                  12884901888,  // 12GiB
                  13958643712,  // 13GiB
                  15032385536,  // 14GiB
                  16106127360,  // 15GiB
                  17179869184,  // 16GiB
                  34359738368,  // 32GiB
                  ],
  disk_values: [536870912, // 512MiB
                1073741824,  // 1GiB
                2147483648,  // 2GiB
                3221225472,  // 3GiB
                4294967296,  // 4GiB
                5368709120,  // 5GiB
                16106127360,  // 15GiB
                21474836480,  // 20GiB
                32212254720,  // 30GiB
                42949672960,  // 40GiB
                53687091200,  // 50GiB
                80530636800,  // 750GiB
                107374182400,  // 100GiB
                134217728000,  // 125GiB
                161061273600,  // 150GiB
                214748364800,  // 200GiB
                268435456000,  // 250GiB
                ],
  yes_no(value, value_yes, value_no) {
    if (!value_yes)
      value_yes = "yes";
    if (!value_no)
      value_no = "no";
    return value ? value_yes : value_no;
  },
  standardHTTPError(response) {
    let statuses = {
      // 1××: Informational
      100: "Continue",
      101: "Switching Protocols",
      102: "Processing",
      
      // 2××: Success
      200: "OK",
      201: "Created",
      202: "Accepted",
      203: "Non-authoritative Information",
      204: "No Content",
      205: "Reset Content",
      206: "Partial Content",
      207: "Multi-Status",
      208: "Already Reported",
      226: "IM Used",
      
      // 3××: Redirection
      300: "Multiple Choices",
      301: "Moved Permanently",
      302: "Found",
      303: "See Other",
      304: "Not Modified",
      305: "Use Proxy",
      307: "Temporary Redirect",
      308: "Permanent Redirect",
      
      // 4××: Client Error
      400: "Bad Request",
      401: "Unauthorized",
      402: "Payment Required",
      403: "Forbidden",
      404: "Not Found",
      405: "Method Not Allowed",
      406: "Not Acceptable",
      407: "Proxy Authentication Required",
      408: "Request Timeout",
      409: "Conflict",
      410: "Gone",
      411: "Length Required",
      412: "Precondition Failed",
      413: "Payload Too Large",
      414: "Request-URI Too Long",
      415: "Unsupported Media Type",
      416: "Requested Range Not Satisfiable",
      417: "Expectation Failed",
      418: "I'm a teapot",
      421: "Misdirected Request",
      422: "Unprocessable Entity",
      423: "Locked",
      424: "Failed Dependency",
      426: "Upgrade Required",
      428: "Precondition Required",
      429: "Too Many Requests",
      431: "Request Header Fields Too Large",
      444: "Connection Closed Without Response",
      451: "Unavailable For Legal Reasons",
      499: "Client Closed Request",
      
      //5××: Server Error
      500: "Internal Server Error",
      501: "Not Implemented",
      502: "Bad Gateway",
      503: "Service Unavailable",
      504: "Gateway Timeout",
      505: "HTTP Version Not Supported",
      506: "Variant Also Negotiates",
      507: "Insufficient Storage",
      508: "Loop Detected",
      510: "Not Extended",
      511: "Network Authentication Required",
      599: "Network Connect Timeout Error",
    };

    if (response === undefined) { // no response
                                  //usually due to browser blocking failed OPTION preflight request
      return "Cross-Origin Request Blocked: preflight request failed."
    }
    let status_text = response.statusText ? response.statusText : statuses[response.status];
    return response.status + ": " + status_text + ".";
  },
  format_dt: format_dt,
  format_duration: format_duration,
  format_duration_between: format_duration_between,
  params_serializer:params_serializer,
  now: now,
  image_human: image_human,
  build_docker_command: build_docker_command,
  trim_command: trim_command,
  from_now: from_now,
  short_id: short_id,
  filesize: filesize2,
  duplicate: duplicate,
};
