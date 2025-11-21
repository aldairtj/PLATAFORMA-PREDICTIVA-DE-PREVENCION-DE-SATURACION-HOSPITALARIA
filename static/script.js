document.addEventListener('DOMContentLoaded', () => {

    // --- Datos Simulados (Predicciones) ---

    // 1. Datos para la Gráfica de Predicción UCI (Línea)
    const uciPredictionData = {
        labels: ["0h", "6h", "12h", "18h", "24h", "30h", "36h", "42h", "48h"],
        datasets: [
            {
                label: 'Ocupación Actual',
                data: [70, 72, 75, 78, 80, null, null, null, null], // Datos actuales hasta 24h
                borderColor: '#1e88e5', // Azul principal
                backgroundColor: 'rgba(30, 136, 229, 0.1)',
                tension: 0.4,
                fill: false, // No fill para esta línea
                pointBackgroundColor: '#1e88e5',
                pointBorderColor: '#fff',
                pointRadius: 5,
                spanGaps: true // Permite gaps en la línea
            },
            {
                label: 'Predicción IA',
                data: [null, null, null, null, 80, 85, 88, 86, 89], // Predicción desde las 24h
                borderColor: '#ffc107', // Amarillo para la predicción
                backgroundColor: 'rgba(255, 193, 7, 0.1)',
                borderDash: [5, 5], // Línea punteada
                tension: 0.4,
                fill: false,
                pointBackgroundColor: '#ffc107',
                pointBorderColor: '#fff',
                pointRadius: 5,
                spanGaps: true
            }
        ]
    };

    // 2. Datos para la Gráfica Comparativa (Barras)
    const comparativeData = {
        labels: ["H. Central", "H. Norte", "H. Sur", "H. Este"],
        datasets: [
            {
                label: 'Actual %',
                data: [85, 72, 58, 91],
                backgroundColor: '#28a745', // Verde para actual
                borderColor: '#28a745',
                borderWidth: 1
            },
            {
                label: 'Predicción 24h %',
                data: [98, 78, 62, 96],
                backgroundColor: '#1e88e5', // Azul para predicción
                borderColor: '#1e88e5',
                borderWidth: 1
            }
        ]
    };

    // --- Configuración y Renderizado de Gráficas (Predicciones) ---

    // 1. Gráfica de Predicción UCI (Línea)
    const uciPredictionChartElement = document.getElementById('uciPredictionChart');
    if (uciPredictionChartElement) {
        new Chart(uciPredictionChartElement, {
            type: 'line',
            data: uciPredictionData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false,
                        max: 100,
                        min: 0,
                        ticks: { stepSize: 25 }
                    },
                    x: {
                        grid: { display: true } // Mantener grid horizontal para las horas
                    }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                }
            }
        });
    }

    // 2. Gráfica Comparativa (Barras)
    const comparativeChartElement = document.getElementById('comparativeChart');
    if (comparativeChartElement) {
        new Chart(comparativeChartElement, {
            type: 'bar',
            data: comparativeData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        min: 0,
                        ticks: { stepSize: 25 }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                }
            }
        });
    }

    // --- Lógica del Dashboard de Inicio (Si aún está en index.html) ---
    // (Mantén el código anterior de index.html si lo necesitas en ese archivo)
    const uciDataDashboard = {
        labels: ["Lun", "Mar", "Mié", "Jue", "Vie"],
        datasets: [{
            label: 'Ocupación %',
            data: [72, 70, 75, 82, 78],
            borderColor: '#1e88e5',
            backgroundColor: 'rgba(30, 136, 229, 0.1)',
            tension: 0.4,
            fill: true,
            pointBackgroundColor: '#1e88e5',
            pointBorderColor: '#fff',
            pointRadius: 5
        }]
    };

    const hospitalDataDashboard = {
        labels: ["H. Central", "H. Este", "H. Norte"],
        datasets: [{
            label: 'Ocupación %',
            data: [95, 98, 85],
            backgroundColor: ["#3f51b5", "#ffc107", "#4caf50"],
            borderColor: ["#3f51b5", "#ffc107", "#4caf50"],
            borderWidth: 1,
            barPercentage: 0.7,
            categoryPercentage: 0.8
        }]
    };

    const uciChartElementDashboard = document.getElementById('uciEvolutionChart');
    if (uciChartElementDashboard) {
        new Chart(uciChartElementDashboard, {
            type: 'line',
            data: uciDataDashboard,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: false, max: 100, min: 0, ticks: { stepSize: 25 } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { display: false }, title: { display: false } }
            }
        });
    }

    const hospitalChartElementDashboard = document.getElementById('hospitalOccupancyChart');
    if (hospitalChartElementDashboard) {
        new Chart(hospitalChartElementDashboard, {
            type: 'bar',
            data: hospitalDataDashboard,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'x',
                scales: {
                    y: { beginAtZero: true, max: 100, min: 0, ticks: { stepSize: 25 } },
                    x: { grid: { display: false } }
                },
                plugins: { legend: { display: false }, title: { display: false } }
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');

    // Función para mostrar la pestaña activa
    function showTab(tabId) {
        // 1. Ocultar todos los contenidos de pestaña y quitar clase 'active'
        tabPanes.forEach(pane => {
            pane.style.display = 'none';
            pane.classList.remove('active');
        });

        // 2. Desactivar todos los botones
        tabButtons.forEach(button => {
            button.classList.remove('active');
        });

        // 3. Mostrar el contenido de la pestaña seleccionada
        const activePane = document.getElementById(tabId);
        if (activePane) {
            // Utilizamos un pequeño retraso para asegurar que la animación CSS se dispare
            activePane.style.display = 'block'; 
            setTimeout(() => {
                activePane.classList.add('active');
            }, 50);
        }
    }

    // Event Listeners para cada botón de pestaña
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 4. Activar el botón clicado
            this.classList.add('active');

            // Obtener el ID de la pestaña de destino (por ejemplo: 'general', 'security')
            const targetTabId = this.getAttribute('data-tab');
            showTab(targetTabId);
        });
    });

    // Inicializar: Mostrar la primera pestaña por defecto al cargar
    if (tabButtons.length > 0) {
        tabButtons[0].click(); // Simular clic en el primer botón para inicializar
    }
});