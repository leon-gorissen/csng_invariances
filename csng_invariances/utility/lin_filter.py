"""Provide different linear filters to estimate a linear receptive field."""
# TODO multiprocessing
import numpy as np
from numpy.linalg import pinv
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from rich import print
from rich.progress import track
from pathlib import Path

import torch


figure_sizes = {
    "full": (8, 5.6),
    "half": (5.4, 3.8),
}


def _reshape_filter_2d(fil):
    """Reshape filter to 2D representation

    Args:
        fil (np.array): 4D representation of filter

    Returns:
        np.array: 2D representation of array
    """
    # TODO make class method.
    assert len(fil.shape) == 4, f"Filter was expected to be 4D but is {fil.shape}"
    neuron_count = fil.shape[0]
    dim1 = fil.shape[2]
    dim2 = fil.shape[3]
    fil = fil.squeeze()
    fil = fil.reshape(neuron_count, dim1 * dim2)
    fil = np.moveaxis(fil, [0, 1], [1, 0])
    return fil


class Filter:
    """Class of linear filters for lin. receptive field approximation."""

    def __init__(self, images, responses, reg_type, reg_factor):
        """Infilterntiates Class

        Args:
            images (np.array): image self.report_data
            responses (np.array): response self.report_data
            reg_type (str, optional): Type of regularization used to compute filter.
                Options are:
                    - "laplace regularied",
                    - "ridge regularized",
                    - "whitened",
                    - "raw".
                Defaults to "laplace regularized".
            reg_factor (optional): Regularization factor.
        """
        # Instanatiate attributes from arguments
        self.images = images
        self.image_count = images.shape[0]
        self.channels = images.shape[1]
        self.dim1 = images.shape[2]
        self.dim2 = images.shape[3]
        self.responses = responses
        self.neuron_count = self.responses.shape[1]
        self.reg_factor = reg_factor
        self.reg_type = reg_type
        assert self.reg_type in set(
            ["laplace regularized", "ridge regularized", "whitened", "raw"]
        ), "No valid type option. Options are 'laplace regularized', \
            'ridge regularized', 'whitened' and 'raw'."
        # Laplace regularized case
        if self.reg_type == "laplace regularized":
            self._compute_filter = self._laplace_regularized_filter
        # ridge regularized case
        elif self.reg_type == "ridge regularized":
            self._compute_filter = self._ridge_regularized_filter
        # whitened case
        elif self.reg_type == "whitened":
            self._compute_filter = self._whitened_filter
        # base case
        else:
            self._compute_filter = self._normal_filter

        # instantiate attributes
        self.time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S"))
        self.model_dir = Path.cwd() / "models" / "linear_filter" / self.time
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = None
        self.figure_dir = None
        self.fil = None
        self.prediction = None
        self.corr = None

    def train(self):
        None

    def predict(self, fil=None, single_neuron_correlation=False):
        """Predict response on filter.

        If no filter is passed, the computed filter is used.

        Args:
            fil (np.array, optional): Filter to use for prediction. Defaults to
                None.
            singel_neuron_correlation (bool, optional): If True, compute single
                neuron correlation. Defaults to False.

        Returns:
            tuple: tuple of predictions and correlation
        """
        fil = self._handle_predict_parsing(fil)
        self._image_2d()
        self.prediction = np.asarray(np.matmul(self.images, fil))
        self.corr = np.corrcoef(self.prediction.flatten(), self.responses.flatten())[
            0, 1
        ]
        if single_neuron_correlation:
            self.single_neuron_correlations = np.empty(self.neuron_count)
            for neuron in range(self.neuron_count):
                pred = self.prediction[:, neuron]
                resp = self.responses[:, neuron]
                single_corr = np.corrcoef(pred, resp)[0, 1]
                self.single_neuron_correlations[neuron] = single_corr
        return self.prediction, self.corr

    def evaluate(self, fil=None, reports=True, store_images=False, report_dir=None):
        """Generate fit report of Filter.

        If no filter is passed, the computed filter is used.

        Args:
            fil (np.array, optional): Filter to use for report. Defaults to None.
            reports (bool, optional): If True evaluation reports are stored.
                Defaults to True.
            store_images (bool, optional): If True images of lin. receptive fields
                and their correlation are depicted. Defaults to False.
            report_dir (Path, optional): Path to use to store report. Defaults
                to None.

        Returns:
            dict: Dictionary of Neurons and Correlations
        """
        if report_dir is None:
            self.report_dir = Path.cwd() / "reports" / "linear_filter" / self.time
            self.report_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.report_dir = report_dir
        computed_prediction = self._handle_evaluate_parsing(fil)
        fil = _reshape_filter_2d(fil)
        # Make report
        self.neural_correlations = {}
        print("Begin reporting procedure.")
        if store_images:
            print(f"Stored images at {self.figure_dir}.")
        for neuron in track(range(computed_prediction.shape[1])):
            corr = np.corrcoef(
                computed_prediction[:, neuron], self.responses[:, neuron]
            )[0, 1]
            if store_images:
                self.figure_dir = (
                    Path.cwd() / "reports" / "figures" / "linear_filter" / self.time
                )
                self.figure_dir.mkdir(parents=True, exist_ok=True)
                fig, ax = plt.subplots(figsize=figure_sizes["half"])
                im = ax.imshow(fil[:, neuron].reshape(self.dim1, self.dim2))
                ax.set_title(f"Neuron: {neuron} | Correlation: {round(corr*100,2)}%")
                fig.colorbar(im)
                plt.savefig(
                    self.figure_dir / f"Filter_neuron_{neuron}.svg",
                    bbox_inches="tight",
                )
                plt.close()
            self.neural_correlations[neuron] = corr
        self.fil = fil
        self._fil_4d()
        if reports:
            print(f"Reports are stored at {self.report_dir}")
            with open(self.report_dir / "Correlations.csv", "w") as file:
                for key in self.neural_correlations:
                    file.write("%s,%s\n" % (key, self.neural_correlations[key]))
            print(f"Filter is stored at {self.model_dir}")
            np.save(str(self.model_dir / "evaluated_filter.npy"), self.fil)
            with open(self.model_dir / "readme.txt", "w") as file:
                file.write(
                    (
                        "evaluated_filter.npy contains a 4D representation "
                        "of a linear filter used to estimate the linear "
                        "receptive field of neurons.\nThe dimension are: "
                        f"(neuron, channels, dim1, dim2): {self.fil.shape}"
                    )
                )
        print("Reporting procedure concluded.")
        return self.neural_correlations

    def select_neurons(self):
        # TODO neuron selection process
        pass

    def _shape_printer(self):
        """Print shape related information for debugging."""
        print(
            f"The current image shape is {self.images.shape}\
              \nand the response shape is {self.responses.shape}."
        )
        if self.fil is None:
            print("No filter has yet been computed.")
        else:
            print(f"The current filter shape is {self.fil.shape}.")
        if self.prediction is None:
            print("No predictions have been computed yet.")
        else:
            print(f"The current prediction shape is {self.prediction.shape}")

    def _image_2d(self):
        """Reshape image self.report_dataset to 2D representation."""
        self.images = self.images.reshape(self.image_count, self.dim1 * self.dim2)

    def _fil_2d(self):
        """Reshape filter self.report_dataset to 2D representation."""
        if len(self.fil.shape) == 4:
            assert (
                len(self.fil.shape) == 4
            ), f"The filter was expected to be 4D but is of shape {self.fil.shape}."
            self.fil = self.fil.squeeze()
            self.fil = self.fil.reshape(self.neuron_count, self.dim1 * self.dim2)
            self.fil = np.moveaxis(self.fil, [0, 1], [1, 0])

    def _fil_4d(self):
<<<<<<< HEAD
        """Reshape filter dataset to 4D representation."""
        self.fil = self.fil.numpy()
=======
        """Reshape filter self.report_dataset to 4D representation."""
>>>>>>> e69bf1503673fd173a6ae273fb835fc7625eea48
        if len(self.fil.shape) == 2:
            if torch.is_tensor(self.fil):
                self.fil = self.fil.numpy()
            self.fil = np.moveaxis(self.fil, [0, 1], [1, 0])
            self.fil = self.fil.reshape(
                self.neuron_count,
                self.channels,
                self.dim1,
                self.dim2,
            )

    def _normal_filter(self, responses, **kwargs):
        """Compute Spike-triggered Average.

        Args:
            responses (np.array): 2D representation of the response self.report_data.

        Returns:
            np.array: 2D representation of linear filters.  Filters are flattened.
        """
        self._image_2d()
        fil = np.matmul(self.images.T, responses)
        return fil

    def _whitened_filter(self, responses, **kwargs):
        """Compute whitened Spike-triggered Average.

        Args:
            responses (np.array): 2D representation of the response self.report_data.

        Returns:
            np.array: 2D representation of linear filters. Filters are flattened.
        """
        self._image_2d()
        fil = np.matmul(
            pinv(np.matmul(self.images.T, self.images)),
            np.matmul(self.images.T, responses),
        )
        return fil

    def _ridge_regularized_filter(self, responses, reg_factor):
        """Compute ridge regularized spike-triggered average.

        Args:
            responses (np.array): 2D representation of the response self.report_data.
            reg_factor (float): regularization factor.

        Returns:
            np.array: 2D representation of linear filters. Filters are flattened.
        """
        self._image_2d()
        fil = np.matmul(
            pinv(
                np.matmul(self.images.T, self.images)
                + reg_factor * np.identity(self.dim1 * self.dim2)
            ),
            np.matmul(self.images.T, responses),
        )
        return fil

    def _laplace_regularized_filter(self, responses, reg_factor):
        # TODO There is an error in the math for the filter computation. It works
        # correctly for square images. However, for non square images only a
        # subset of the image is correctly regularized.
        print(
            "Laplace regularization is not correctly implemented! Only square images are regularized as expected."
        )
        """Compute laplace regularized spike-triggered average

        Args:
            responses (np.array): 2D representation of the response self.report_data.
            reg_factor (float): Regularization factor.

        Returns:
            np.array: 2D representation of linear filter. Filters are flattened.
        """

        def __laplaceBias(sizex, sizey):
            """Generate matrix based on discrete laplace operator with sizex * sizey.

            Args:
                sizex (int): x-dimension of to be regularized object
                sizey (int): y-dimension of to be regularized object

            Returns:
                np.matrix: matrix based on laplace operator
            """
            S = np.zeros((sizex * sizey, sizex * sizey))
            for x in range(0, sizex):
                for y in range(0, sizey):
                    norm = np.mat(np.zeros((sizex, sizey)))
                    norm[x, y] = 4
                    if x > 0:
                        norm[x - 1, y] = -1
                    if x < sizex - 1:
                        norm[x + 1, y] = -1
                    if y > 0:
                        norm[x, y - 1] = -1
                    if y < sizey - 1:
                        norm[x, y + 1] = -1
                    S[x * sizex + y, :] = norm.flatten()
            S = np.mat(S)
            return S

        self._image_2d()
        laplace = __laplaceBias(self.dim1, self.dim2)
        print(self.images.shape)
        print(laplace.shape)
        X = self.images
        y = self.responses
        # ti = np.vstack((self.images, np.dot(float(reg_factor), laplace)))
        # ts = np.vstack(
        #     (
        #         responses,
        #         np.zeros((self.images.shape[1], responses.shape[1])),
        #     )
        # )
        # fil = np.asarray(pinv(ti.T * ti) * ti.T * ts)
        # (X.T*X+L*M)^-1*X.T*y
        reg_matrix = np.dot(reg_factor, laplace)
        inv = np.matmul(X.T, X) + reg_matrix
        inv = np.linalg.pinv(inv)
        A = np.matmul(inv, X.T)
        fil = np.matmul(A, y)
        return fil

    def _handle_train_parsing(self, reg_factor):
        """Handle parsing of a regularization factor during `train()`.

        Args:
            reg_factor (float): Regularization factor.
        """
        if reg_factor is None:
            reg_factor = self.reg_factor
        return reg_factor

    def _handle_predict_parsing(self, fil):
        """Handle parsing of filters during `predict()`

        Args:
            fil (np.array): 4D representation of linear filters.
        """
        if fil is None:
            if self.fil is None:
                self.train()
            self._fil_2d()
            fil = self.fil
        if len(fil.shape) == 4:
            fil = _reshape_filter_2d(fil)
        return fil

    def _handle_evaluate_parsing(self, fil):
        """Handle parsing of filters during `evaluate()`.

        Args:
            fil (np.array): 4D-representation of filters.

        Returns:
            np.array: predictions.
        """
        if fil is None:
            if self.fil is None:
                self.fil = self.train()
            if self.prediction is None:
                self.predict()
            fil = self.fil
            computed_prediction = self.prediction
        else:
            if len(fil.shape) == 4:
                fil = _reshape_filter_2d(fil)
            computed_prediction, _ = self.predict(fil)

        return computed_prediction


class GlobalRegularizationFilter(Filter):
    """Global regularized linear filter class.

    Class of linear filters with global regularization factor applied."""

    def __init__(self, images, responses, reg_type="ridge regularized", reg_factor=10):
        super().__init__(images, responses, reg_type, reg_factor)

    def train(self, reg_factor=None):
        """Compute linear filters fitting images to neural responses.

        Args:
            reg_factor (float, optional): Regularization factor. Defaults to None.

        Returns:
            np.array: 4D representation of filter.
        """
        reg_factor = self._handle_train_parsing(reg_factor)
        self._image_2d()
        self._shape_printer()
        self.fil = self._compute_filter(responses=self.responses, reg_factor=reg_factor)
        self._shape_printer()
        self._fil_4d()
        self._shape_printer()
        return self.fil


class IndividualRegularizationFilter(Filter):
    """Individually regularized linear filter class.

    Class of linear filters with individual regularization factors applied."""

    def __init__(
        self, images, responses, reg_type="ridge regularized", reg_factor=None
    ):
        super().__init__(images, responses, reg_type, reg_factor)
        if reg_factor is None:
            self.reg_factor = [10 for i in range(self.responses.shape[1])]

    def train(self, reg_factors=None):
        """Compute linear filters with individual regularization.

        Args:
            reg_factors (list, optional): List of regularization factors
                (one per neuron). Defaults to None.

        Returns:
            np.array: 2D representation of linear filters. Filters are flattened.
        """
        reg_factors = self._handle_train_parsing(reg_factors)
        filters = np.empty((self.dim1 * self.dim2, self.neuron_count))
        for neuron, reg_factor in zip(range(self.neuron_count), reg_factors):
            self._image_2d()
            response = self.responses[:, neuron].reshape(self.image_count, 1)
            fil = self._compute_filter(responses=response, reg_factor=reg_factor)
            filters[:, neuron] = fil.squeeze()
        self.fil = filters
        self._fil_4d()
        return self.fil


class Hyperparametersearch:
    """Class of hyperparametersearches of linear filters."""

    def __init__(self, TrainFilter, ValidationFilter, reg_factors, report=True):
        self.TrainFilter = TrainFilter
        self.ValidationFilter = ValidationFilter
        self.reg_factors = reg_factors
        self.report = report
        self.neuron_count = self.TrainFilter.neuron_count
        self.neurons = np.array(list(range(self.neuron_count))).reshape(
            self.neuron_count, 1
        )
        self.time = str(datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S"))

    def conduct_search(self):
        None

    def compute_best_parameter(self):
        """Pick best regularization factors.

        Returns:
            tuple: Tuple of array [neuron col vector, regularization col vector
                correlation col vector] and average correlation.
        """
        self.hyperparameters = np.empty(self.neuron_count)
        mask = self.df_corrs.eq(self.df_corrs.max(axis=1), axis=0)
        masked = self.df_params[mask].values.flatten()
        self.hyperparameters = masked[masked == masked.astype(float)].reshape(
            self.neuron_count, 1
        )
        self.single_neuron_correlations = self.df_corrs.max(axis=1).values
        self.single_neuron_correlations = self.single_neuron_correlations.reshape(
            self.neuron_count, 1
        )
        self.results = np.hstack(
            (self.neurons, self.hyperparameters, self.single_neuron_correlations)
        )
        self.avg_correlation = self.df_corrs.max(axis=1).mean()
        if self.report:
            np.save(self.report_dir / "hyperparametersearch_report.npy", self.results)
            with open(self.report_dir / "readme.txt", "w") as f:
                f.write(
                    (
                        "hyperparametersearch_report "
                        ".npy contains a 2D array, where column one represents the "
                        "the neurons, column two the regularization factor and "
                        "column three the single neuron correlation of the filter "
                        "prediction and the real responses."
                    )
                )
        return self.results, self.avg_correlation

    def get_parameters(self):
        None


class GlobalHyperparametersearch(Hyperparametersearch):
    """Hyperparametersearch for globally regularized linear filters."""

    def __init__(self, TrainFilter, ValidationFilter, reg_factors, report=True):
        super().__init__(TrainFilter, ValidationFilter, reg_factors, report=report)
        self.report_dir = (
            Path.cwd()
            / "reports"
            / "linear_filter"
            / "global_hyperparametersearch"
            / self.time
        )
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def conduct_search(self):
        """Conduct hyperparametersearch.

        Returns:
            ndarray: Array of with coloumns: neurons, parameters and correlations.
                Parameters and correlations are 2D arrays themselves.
        """
        self.params = np.empty((self.neuron_count, len(self.reg_factors)))
        self.corrs = np.empty((self.neuron_count, len(self.reg_factors)))
        self.c = np.empty(len(self.reg_factors))
        print("Beginning hyperparametersearch.")
        for counter, reg_factor in track(
            enumerate(self.reg_factors), total=len(self.reg_factors)
        ):
            filter = self.TrainFilter.train(reg_factor)
            print(filter.shape)
            _, corr = self.ValidationFilter.predict(filter)
            self.c[counter] = corr
        print("Hyperparametersearch concluded.")
        for neuron in range(self.neuron_count):
            self.params[neuron] = self.reg_factors
            self.corrs[neuron] = self.c
        self.df_params = pd.self.report_dataFrame(self.params, columns=self.reg_factors)
        self.df_corrs = pd.self.report_dataFrame(self.corrs, columns=self.reg_factors)
        self.search = np.hstack((self.neurons, self.params, self.corrs))
        return self.search

    def get_parameters(self):
        """Get optimized hyperparameters."""
        return self.hyperparameters[0]


class IndividualHyperparametersearch(Hyperparametersearch):
    """Class of hyperparametersearch for single neuron regularized linear filters."""

    def __init__(self, TrainFilter, ValidationFilter, reg_factors, report=True):
        super().__init__(TrainFilter, ValidationFilter, reg_factors, report=report)
        self.report_dir = (
            Path.cwd()
            / "reports"
            / "linear_filter"
            / "individual_hyperparametersearch"
            / self.time
        )
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def conduct_search(self):
        self.params = np.empty((self.neuron_count, len(self.reg_factors)))
        self.corrs = np.empty((self.neuron_count, len(self.reg_factors)))
        print("Beginning hyperparametersearch.")
        for counter, reg_factor in track(
            enumerate(self.reg_factors), total=len(self.reg_factors)
        ):
            reg_factor = [reg_factor for i in range(self.neuron_count)]
            filter = self.TrainFilter.train(reg_factor)
            self.ValidationFilter.predict(filter, True)
            self.params[:, counter] = reg_factor
            self.corrs[:, counter] = self.ValidationFilter.single_neuron_correlations
        print("Hyperparametersearch concluded.")
        self.df_params = pd.self.report_dataFrame(self.params, columns=self.reg_factors)
        self.df_corrs = pd.self.report_dataFrame(self.corrs, columns=self.reg_factors)
        self.search = np.hstack((self.neurons, self.params, self.corrs))
        return self.search

    def get_parameters(self):
        """Get optimized hyperparameters."""
        return self.hyperparameters


class FilterReport:
    def __init__(self, report_file, counter):
        self.counter = counter
        self.report_file = report_file
        (
            cwd,
            reports_dir,
            fil_type,
            reg_type,
            date_time,
            file_name,
        ) = self.report_file.rsplit("/", 5)
        self.correlation_file = (
            Path.cwd()
            / reports_dir
            / fil_type
            / reg_type
            / date_time
            / "Correlations.csv"
        )
        self.report_figure_path = (
            Path.cwd() / reports_dir / "figures" / fil_type / reg_type / date_time
        )
        self.report_figure_path.mkdir(parents=True, exists_ok=True)
        self.filter_file = (
            Path.cwd() / "models" / fil_type / date_time / "evaluated_filter.npy"
        )

    def analyze(self, save=True):
        """Analyze report files.

        Sorts neuron in descending single neuron correlation order and computes
        average correlation.

        Args:
            save (bool, optional): If True, analyzis is stored. Defaults to True.
        """
        self.report_data = np.load(self.report_file)
        df = pd.DataFrame(
            self.report_data, columns=["Neuron", "RegFactor", "Correlation"]
        )
        df.drop(columns=["Correlation"])
        report_path, _ = self.report_file.rsplit("/", 1)
        corrs = pd.read_csv(report_path + "/Correlations.csv")
        corrs_1 = [float(corrs.columns[1])]
        corrs_1.extend(corrs.iloc[:, 1].to_list())
        df["Correlation"] = corrs_1
        df = df.sort_values(["Correlation"], ascending=False, ignore_index=True)
        self.avg_correlation = df.Correlation.sum() / len(df.Correlation)
        if save:
            with open(self.report_path + "/average_correlation.txt", "w") as f:
                f.write(str(self.avg_correlation))
            sort = df.values
            np.save(
                self.report_path + "/hyperparametersearch_report_descending.npy",
                sort,
            )

    def plot_individual(self):
        """Plots and stores"""
        self.filter_data = np.load(self.filter_file)
        for i in range(self.counter):
            corr = self.df.Correlation.iloc[i]
            neuron = int(self.df.Neuron.iloc[i])
            fil = self.filter_data[neuron, 0, :, :]
            plt.imshow(fil)
            plt.savefig(self.report_figure_path / f"Filter_{i}.png")


if __name__ == "__main__":
    pass
