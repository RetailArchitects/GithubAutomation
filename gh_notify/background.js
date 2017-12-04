var socket = io.connect("http://5d91002d.ngrok.io");

socket.on('connect', function(data) {
  var gh_user = chrome.storage.sync.get(null, function(items) {
    socket.emit('store-client-data', { gh_user: items.gh_user });
  });
});

socket.on('display-notification', function(data) {
  var opt = {
    type: "basic",
    title: data.title,
    message: data.message,
    iconUrl: "ra_logo_square.png"
  }

  chrome.notifications.create(null, opt, null);
});