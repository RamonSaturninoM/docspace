/* TAB SWITCHING */

function showTab(tabId){

document.querySelectorAll('.tab-panel')
.forEach(panel => panel.classList.add('hidden'));

document.getElementById(tabId).classList.remove('hidden');

document.querySelectorAll('.tab')
.forEach(tab => tab.classList.remove('active'));

event.target.classList.add('active');
}


/* SETTINGS DROPDOWN */

function toggleSettingsMenu(){
document.getElementById("settingsMenu")
.classList.toggle("hidden");
}