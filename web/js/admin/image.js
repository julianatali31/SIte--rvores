// Shrinks a photo in the browser when it is above the upload limit
// (Vercel accepts ~4.5 MB per request). The server still re-encodes and strips metadata.
const MAX_SIDE = 2048;

async function toJpeg(file, quality) {
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
}

export async function fitForUpload(file, maxMb) {
  const limit = maxMb * 1024 * 1024;
  if (file.size <= limit) return file;
  for (const quality of [0.88, 0.75, 0.6]) {
    const blob = await toJpeg(file, quality);
    if (blob && blob.size <= limit) {
      return new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' });
    }
  }
  throw new Error(`Foto grande demais mesmo reduzida (limite ${maxMb} MB).`);
}
