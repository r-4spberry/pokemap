A simple tool that loads an image, extracts wall contours, allows area selection, and exports the data as JSON.

## Usage

1. **Load an Image**  
   Click on **Load Image** and choose an image file.

2. **Select Areas**  
   Click on **Pick Area A** or **Pick Area B** and select two corners on the image to define the area.

3. **Save the Result**  
   Click **Save** to export the wall and area data along with the image (encoded in base64) as a JSON file.

   ## JSON Structure

A saved JSON file has the following structure:

```json
{
  "walls": [
    {
      "x1": 10,
      "y1": 20,
      "x2": 50,
      "y2": 60,
      "nx": 0.0,
      "ny": 1.0,
      "outer": true
    }
  ],
  "areas": [
    {
      "name": "A",
      "x1": 100,
      "y1": 100,
      "x2": 200,
      "y2": 200
    },
    {
      "name": "B",
      "x1": 250,
      "y1": 250,
      "x2": 350,
      "y2": 350
    }
  ],
  "image": "base64encodedstring"
}
```
