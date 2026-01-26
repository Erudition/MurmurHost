// Local configuration overrides for mumble-web
// This file is loaded after config.js and can override any settings

window.mumbleWebConfig = window.mumbleWebConfig || {};

// Override defaults to use the current connection's port
// This makes it work for both local (8081) and standard HTTPS (443) access
Object.assign(window.mumbleWebConfig.defaults, {
  // Use window.location.port to get the current port, or default to 443 for standard HTTPS
  'port': window.location.port || '443',
  'address': window.location.hostname
});

// You can also set a fixed address and port if needed:
// Object.assign(window.mumbleWebConfig.defaults, {
//   'address': 'your-server-hostname-or-ip',
//   'port': '8081'
// });
