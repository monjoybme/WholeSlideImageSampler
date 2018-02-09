import openslide
import os
import numpy as np
from skimage import filters, color
from skimage.morphology import disk
from skimage.morphology import opening


class Slide_Sampler(object):

    def __init__(self, wsi_file, desired_downsampling, size):
        super(Slide_Sampler, self).__init__()
        self.wsi_file = wsi_file
        self.wsi = openslide.OpenSlide(self.wsi_file)
        self.desired_downsampling = desired_downsampling
        self.size = size
        self.level, self.downsampling = self.get_level_and_downsampling(desired_downsampling, 0.1)
        self.width_available = int(self.wsi.dimensions[0] - self.downsampling * size)
        self.height_available = int(self.wsi.dimensions[1] - self.downsampling * size)
        self.background_mask = None
        print('\nInitialized Slide_Sampler for slide {}'.format(os.path.basename(self.wsi_file)))
        print('Patches will be sampled at level {0} == downsampling of {1}, with size {2} x {2}.'.format(self.level,
                                                                                                         self.downsampling,
                                                                                                         self.size))

    def get_level_and_downsampling(self, desired_downsampling, threshold):
        """
        Get the level and downsampling for a desired downsampling.
        A threshold is used to allow for not exactly equal desired and true downsampling.
        If an appropriate level is not found an exception is raised.
        :return:
        """
        diffs = [abs(desired_downsampling - self.wsi.level_downsamples[i]) for i in
                 range(len(self.wsi.level_downsamples))]
        minimum = min(diffs)
        if minimum > threshold:
            raise Exception(
                '\nLevel not found for desired downsampling.\nAvailable downsampling factors are\n{}'.format(
                    self.wsi.level_downsamples))
        level = diffs.index(minimum)
        return level, self.wsi.level_downsamples[level]

    def add_background_mask(self, desired_downsampling=32, threshold=4, disk_radius=10):
        """
        Add a background mask. That is a binary, downsampled image where True denotes a tissue region.
        This is achieved by otsu thresholding on the saturation channel followed by morphological opening to remove noise.
        The mask desired downsampling factor has a default of 32. For a WSI captured at 40X this corresponds to 1.25X.
        :param desired_downsampling:
        :param threshold:
        :param disk_radius:
        :return:
        """
        print('\nGetting background mask...')
        self.background_mask_level, self.background_mask_downsampling = self.get_level_and_downsampling(
            desired_downsampling, threshold)
        low_res = self.wsi.read_region(location=(0, 0), level=self.background_mask_level,
                                       size=self.wsi.level_dimensions[self.background_mask_level]).convert('RGB')
        low_res_numpy = np.asarray(low_res)
        low_res_numpy_hsv = color.convert_colorspace(low_res_numpy, 'RGB', 'HSV')
        saturation = low_res_numpy_hsv[:, :, 1]
        value = filters.threshold_otsu(saturation)
        mask = (saturation > value)
        selem = disk(disk_radius)
        mask = opening(mask, selem)
        self.background_mask = mask.astype(np.uint8)
        self.size_at_background_level = self.level_converter(self.size, self.level, self.background_mask_level)

    def get_patch(self):
        """
        Get a random patch from the WSI
        :return:
        """
        done = 0
        while not done:
            w = np.random.choice(self.width_available)
            h = np.random.choice(self.height_available)
            patch = self.wsi.read_region(location=(w, h), level=self.level, size=(self.size, self.size)).convert('RGB')
            if self.background_mask==None:
                done=1
            else:
                i = self.level_converter(h, 0, self.background_mask_level)
                j = self.level_converter(w, 0, self.background_mask_level)
                delta = self.size_at_background_level
                background_mask_patch = self.background_mask[i:i + delta, j:j + delta]
                area = background_mask_patch.shape[0] * background_mask_patch.shape[1]
                if np.sum(background_mask_patch) / area > 0.9: done = 1
        return patch

    def print_slide_properties(self):
        """
        Print some WSI properties
        :return:
        """
        print('\nSlide properties.')
        print('Dimensions as level 0:')
        print(self.wsi.dimensions)
        print('Number of levels:')
        print(self.wsi.level_count)
        print('with downsampling factors:')
        print(self.wsi.level_downsamples)

    def level_converter(self, x, lvl_in, lvl_out):
        """
        Convert a coordinate 'x' from lvl_in to lvl_out
        :param x:
        :param lvl_in:
        :param lvl_out:
        :return:
        """
        return np.floor(x * self.wsi.level_downsamples[lvl_in] / self.wsi.level_downsamples[lvl_out]).astype(np.uint32)


###

data_dir = '/media/peter/HDD 1/datasets_peter/Camelyon16/Train/Original/Tumor'
file = os.path.join(data_dir, 'Tumor_001.tif')
mask_file = os.path.join(data_dir, 'Mask_Tumor', 'Tumor_001.tif')

sampler = Slide_Sampler(file, 4, 256)

sampler.print_slide_properties()

sampler.get_background_mask()

import matplotlib.pyplot as plt

mask = sampler.background_mask
plt.imshow(mask)
plt.show()

c = 2
