# Dataset

The images used in this project originate from the [NUS Global Streetscapes dataset](https://github.com/ualsg/global-streetscapes), which was published by the National University of Singapore. The dataset contains large-scale street-level imagery with a variety of labels. For this project, these labels were combined into a single large table that includes the complete set of images and metadata.

This table was exported into a PostgreSQL database in order to enable flexible queries and the creation of subsets. Subsets allow us to work with smaller samples while maintaining the richness of the original dataset. For testing purposes, a subset focusing on Berlin was created.

---

## Steps for preparing the subset

1. **Image quality filtering**  
   Each image in the dataset includes a quality score between 0 and 1.  
   Only images with a score ≥ 0.95 were retained. This filtering step removes very few entries, since most images are already of high quality.

2. **Grouping by location and heading**  
   To avoid using the same image multiple times, images were grouped based on spatial proximity and viewing direction.  
   - Images within a radius of 0.5 meters were treated as one group.  
   - For each group, thumbnails were downloaded using Mapillary’s [API](https://www.mapillary.com/developer/api-documentation) at the *thumb_1024* resolution. This resolution provides a good balance between size and clarity.

3. **Perceptual hashing**  
   To identify visually identical or near-identical images, the Python library [ImageHash](https://github.com/JohannesBuchner/imagehash) was used with the *pHash* (Perceptual Hash) method.  
   Images with nearly identical hashes were considered duplicates and removed from the dataset.

4. **Sharpness filtering**  
   To further refine quality, the Laplacian operator from OpenCV was applied. This method estimates image sharpness.  
   The lowest 20% of images, as measured by this factor, were removed.

---

## Final dataset

The result of these steps is a cleaned and filtered subset of the Global Streetscapes dataset. In the Berlin example, this produced a smaller but higher quality collection of images that can be used for tasks such as pair identification and perception studies.