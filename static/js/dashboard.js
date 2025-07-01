document.addEventListener('DOMContentLoaded', function() {

    const timeEl = document.getElementById('time');
    const dateEl = document.getElementById('date');
    const dashboardEl = document.getElementById('dashboard');
    const screensaverEl = document.getElementById('screensaver');
    const screensaverImg = screensaverEl.querySelector('img');
  
    // Update dashboard time every second
    function updateDashboardTime() {
      const now = new Date();
      if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString('en-GB');
      }
      if (dateEl) {
        const dateOptions = { weekday: 'long', day: 'numeric', month: 'long' };
        let dateStr = now.toLocaleDateString('en-GB', dateOptions);
        dateEl.textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
      }
    }
  
    // Poll server to check if dashboard should be shown or hidden
    let previousModeIsDashboard = false;
    function checkMode() {
      fetch("/mode")
        .then(response => response.json())
        .then(data => {
          const isDashboardMode = data.dashboard;
          if (isDashboardMode) {
            dashboardEl.style.display = "block";
            screensaverEl.style.display = "none";
          } else {
            dashboardEl.style.display = "none";
            screensaverEl.style.display = "block";
  
            // If we just switched FROM dashboard TO screensaver, get a new image
            if (previousModeIsDashboard) {
              fetch("/screensaver_image")
                .then(res => res.json())
                .then(result => {
                  if (result.image_url && screensaverImg) {
                    screensaverImg.src = result.image_url;
                  }
                })
                .catch(err => console.error("Error fetching new screensaver image:", err));
            }
          }
          previousModeIsDashboard = isDashboardMode;
        })
        .catch(err => console.error("Error checking mode:", err));
    }
  
    // Initial calls and intervals
    updateDashboardTime();
    setInterval(updateDashboardTime, 1000);
    
    checkMode();
    setInterval(checkMode, 1000);
  });