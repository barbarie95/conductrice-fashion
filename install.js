(function(){
if(window.matchMedia('(display-mode: standalone)').matches||navigator.standalone)return;
var KEY='cf_install_hide',deferred=null;
try{if(Number(localStorage.getItem(KEY))>Date.now())return}catch(e){}
var ios=/iphone|ipad|ipod/i.test(navigator.userAgent);
var css=document.createElement('style');
css.textContent='#cf-install{position:fixed;left:12px;right:12px;bottom:calc(84px + env(safe-area-inset-bottom));z-index:60;background:#252A34;color:#fff;border-radius:14px;padding:12px 14px;display:flex;align-items:center;gap:10px;box-shadow:0 8px 24px #0004;font-family:Arial,sans-serif;font-size:13px}#cf-install img{width:38px;height:38px;border-radius:9px;object-fit:cover;background:#fff}#cf-install span{flex:1;line-height:1.35}#cf-install button{border:0;border-radius:10px;padding:10px 13px;font-weight:800;font-size:12px;cursor:pointer}#cf-yes{background:#F28C28;color:#fff}#cf-no{background:transparent;color:#fff;font-size:18px;padding:6px 8px}';
document.head.appendChild(css);
function show(text,withBtn){
 if(document.getElementById('cf-install'))return;
 var box=document.createElement('div');box.id='cf-install';
 box.innerHTML='<img src="logo-conductrice-fashion.png" alt=""><span>'+text+'</span>'+(withBtn?'<button id="cf-yes" type="button">Installer</button>':'')+'<button id="cf-no" type="button" aria-label="Fermer">✕</button>';
 document.body.appendChild(box);
 document.getElementById('cf-no').onclick=function(){box.remove();try{localStorage.setItem(KEY,Date.now()+7*864e5)}catch(e){}};
 var yes=document.getElementById('cf-yes');
 if(yes)yes.onclick=function(){if(!deferred)return;deferred.prompt();deferred.userChoice.then(function(){deferred=null;box.remove()})};
}
window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();deferred=e;show('<b>Installer Conductrice Fashion</b><br>Accès direct depuis votre écran d’accueil',true)});
window.addEventListener('appinstalled',function(){var b=document.getElementById('cf-install');if(b)b.remove()});
if(ios)setTimeout(function(){show('<b>Installer Conductrice Fashion</b><br>Touchez <b>Partager</b>, puis <b>Sur l’écran d’accueil</b>',false)},2500);
})();
