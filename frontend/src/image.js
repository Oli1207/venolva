// Réduit une photo avant l'envoi : sur un réseau mobile, un cliché de 5 Mo est inutilement lourd.
const MAX_SIDE = 1280;

export async function shrinkImage(file) {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const ratio = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * ratio);
    canvas.height = Math.round(bitmap.height * ratio);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.82));
    return blob && blob.size < file.size ? new File([blob], "photo.jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file; // le serveur réduit et vérifie de toute façon
  }
}
