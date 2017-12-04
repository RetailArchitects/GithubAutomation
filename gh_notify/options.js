// Saves options to chrome.storage.sync.
function save_options() {
  var gh_user = document.getElementById('gh_user').value;

  chrome.storage.sync.set({
    gh_user: gh_user
  }, function() {
    // Update status to let user know options were saved.
    var status = document.getElementById('status');
    status.textContent = 'Options saved.';
    setTimeout(function() {
      status.textContent = '';
    }, 750);
  });
}

function restore_options() {
  chrome.storage.sync.get(null, function(items) {
    document.getElementById('gh_user').value = items.gh_user;
  });
}
document.addEventListener('DOMContentLoaded', restore_options);
document.getElementById('save').addEventListener('click', save_options);