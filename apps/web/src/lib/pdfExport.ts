import { jsPDF } from 'jspdf'
import { Chart } from 'chart.js/auto'

type Analysis = {
  topics: string[]
  summary: string
  stress_level: 'rendah' | 'sedang' | 'tinggi'
  chat_sentiment?: 'positif' | 'netral' | 'negatif'
  early_actions: string[]
  when_to_seek_help: string[]
  disclaimer: string
}

type FaceData = {
  stressIndex?: number
  level?: string
  blinkPerMin?: number
  blinkPer10s?: number
  jawOpenness?: number
  browTension?: number
}

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

export async function exportToPDF(
  analysis: Analysis,
  faceData: FaceData,
  messages: ChatMessage[]
): Promise<void> {
  const doc = new jsPDF()
  let yPos = 20

  // Title
  doc.setFontSize(20)
  doc.setTextColor(107, 92, 255)
  doc.text('CStress - Laporan Konsultasi', 105, yPos, { align: 'center' })
  yPos += 15

  // Timestamp
  doc.setFontSize(10)
  doc.setTextColor(100, 100, 100)
  doc.text(`Tanggal: ${new Date().toLocaleString('id-ID')}`, 105, yPos, { align: 'center' })
  yPos += 15

  // Stress Level Summary
  doc.setFontSize(14)
  doc.setTextColor(0, 0, 0)
  doc.text('Ringkasan Tingkat Stres', 20, yPos)
  yPos += 10

  doc.setFontSize(11)
  const levelColor = analysis.stress_level === 'tinggi' ? [255, 87, 87] : 
                      analysis.stress_level === 'sedang' ? [255, 187, 56] : 
                      [71, 255, 193]
  doc.setTextColor(...levelColor)
  doc.text(`Tingkat: ${analysis.stress_level.toUpperCase()}`, 20, yPos)
  yPos += 8

  if (analysis.chat_sentiment) {
    doc.setTextColor(100, 100, 100)
    doc.text(`Sentimen Chat: ${analysis.chat_sentiment}`, 20, yPos)
    yPos += 8
  }

  if (faceData.stressIndex !== undefined) {
    doc.text(`Stress Index (Face): ${Math.round(faceData.stressIndex)}/100`, 20, yPos)
    yPos += 15
  } else {
    yPos += 10
  }

  // Create chart if face data available
  if (faceData.stressIndex !== undefined || faceData.blinkPerMin !== undefined) {
    const chartCanvas = document.createElement('canvas')
    chartCanvas.width = 400
    chartCanvas.height = 200
    
    const chartData = []
    const chartLabels = []
    
    if (faceData.stressIndex !== undefined) {
      chartLabels.push('Stress Index')
      chartData.push(faceData.stressIndex)
    }
    if (faceData.blinkPerMin !== undefined) {
      chartLabels.push('Blink/Min')
      chartData.push(faceData.blinkPerMin)
    }
    if (faceData.jawOpenness !== undefined) {
      chartLabels.push('Jaw Tension')
      chartData.push(faceData.jawOpenness * 100)
    }
    if (faceData.browTension !== undefined) {
      chartLabels.push('Brow Tension')
      chartData.push(faceData.browTension * 100)
    }

    const chart = new Chart(chartCanvas, {
      type: 'bar',
      data: {
        labels: chartLabels,
        datasets: [{
          label: 'Indikator Stres',
          data: chartData,
          backgroundColor: [
            'rgba(107, 92, 255, 0.6)',
            'rgba(0, 209, 255, 0.6)',
            'rgba(255, 187, 56, 0.6)',
            'rgba(255, 87, 87, 0.6)'
          ],
          borderColor: [
            'rgb(107, 92, 255)',
            'rgb(0, 209, 255)',
            'rgb(255, 187, 56)',
            'rgb(255, 87, 87)'
          ],
          borderWidth: 2
        }]
      },
      options: {
        responsive: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100
          }
        }
      }
    })

    // Wait for chart to render
    await new Promise(resolve => setTimeout(resolve, 500))
    
    const chartImage = chartCanvas.toDataURL('image/png')
    doc.addImage(chartImage, 'PNG', 20, yPos, 170, 85)
    chart.destroy()
    yPos += 95
  }

  // Topics
  if (yPos > 240) {
    doc.addPage()
    yPos = 20
  }

  doc.setFontSize(12)
  doc.setTextColor(0, 0, 0)
  doc.text('Topik yang Dibahas:', 20, yPos)
  yPos += 8

  doc.setFontSize(10)
  analysis.topics.slice(0, 8).forEach((topic) => {
    if (yPos > 280) {
      doc.addPage()
      yPos = 20
    }
    doc.text(`• ${topic}`, 25, yPos)
    yPos += 6
  })
  yPos += 5

  // Summary
  if (yPos > 240) {
    doc.addPage()
    yPos = 20
  }

  doc.setFontSize(12)
  doc.text('Ringkasan:', 20, yPos)
  yPos += 8

  doc.setFontSize(10)
  const summaryLines = doc.splitTextToSize(analysis.summary, 170)
  summaryLines.forEach((line: string) => {
    if (yPos > 280) {
      doc.addPage()
      yPos = 20
    }
    doc.text(line, 20, yPos)
    yPos += 6
  })
  yPos += 10

  // Early Actions
  if (yPos > 240) {
    doc.addPage()
    yPos = 20
  }

  doc.setFontSize(12)
  doc.text('Langkah Awal yang Disarankan:', 20, yPos)
  yPos += 8

  doc.setFontSize(10)
  analysis.early_actions.slice(0, 6).forEach((action) => {
    const actionLines = doc.splitTextToSize(`• ${action}`, 165)
    actionLines.forEach((line: string) => {
      if (yPos > 280) {
        doc.addPage()
        yPos = 20
      }
      doc.text(line, 25, yPos)
      yPos += 6
    })
  })
  yPos += 10

  // When to Seek Help
  if (yPos > 240) {
    doc.addPage()
    yPos = 20
  }

  doc.setFontSize(12)
  doc.text('Kapan Mencari Bantuan Profesional:', 20, yPos)
  yPos += 8

  doc.setFontSize(10)
  analysis.when_to_seek_help.slice(0, 6).forEach((item) => {
    const itemLines = doc.splitTextToSize(`• ${item}`, 165)
    itemLines.forEach((line: string) => {
      if (yPos > 280) {
        doc.addPage()
        yPos = 20
      }
      doc.text(line, 25, yPos)
      yPos += 6
    })
  })
  yPos += 10

  // Disclaimer
  if (yPos > 260) {
    doc.addPage()
    yPos = 20
  }

  doc.setFontSize(9)
  doc.setTextColor(150, 150, 150)
  const disclaimerLines = doc.splitTextToSize(analysis.disclaimer, 170)
  disclaimerLines.forEach((line: string) => {
    if (yPos > 280) {
      doc.addPage()
      yPos = 20
    }
    doc.text(line, 20, yPos)
    yPos += 5
  })

  // Save
  const filename = `CStress-Laporan-${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(filename)
}
