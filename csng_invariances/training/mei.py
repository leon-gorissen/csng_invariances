"""Module providing Most Exciting Image (MEI) training."""

from pathlib import Path
import torch
from rich.progress import track
import matplotlib.pyplot as plt
from numpy import save
import torchvision
from csng_invariances._utils.utlis import string_time
import wandb


def get_lowpass_tensor(
    image: torch.Tensor, gradient_smoothing_factor: float = 0.1, device: str = None
) -> torch.Tensor:
    """Compute the constant tensor required for lowpass filtering.

    Args:
        image (torch.Tensor): input image
        gradient_smoothing_factor (float, optional): Smoothing factor (in Walker
            et al. refered to as alpha). Defaults to 0.1.
        device (str, optional): If None, tries cuda. Defaults to None.

    Returns:
        torch.Tensor: [description]
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, _, height, width = image.shape
    tw = torch.minimum(
        torch.arange(0, width, 1, dtype=torch.float, device=device),
        torch.arange(width - 1, -1, -1, dtype=torch.float, device=device),
    )
    th = torch.minimum(
        torch.arange(0, height, 1, dtype=torch.float, device=device),
        torch.arange(height - 1, -1, -1, dtype=torch.float, device=device),
    )
    one = torch.ones(1, dtype=torch.float, device=device)
    lowpass = 1 / torch.maximum(
        one, (tw[None, :] ** 2 + th[:, None] ** 2) ** (gradient_smoothing_factor)
    )
    return lowpass


def lowpass_filtering_in_frequency_domain(
    image_grad: torch.Tensor, lowpass: torch.Tensor
) -> torch.Tensor:
    """Applies lowpass filtering in the frequency domain as descibed in Walker
    et al. 2019.

    Args:
        grad (torch.Tensor): gradient
        lowpass (torch.Tensor): losspass tensor (constant)

    Returns:
        torch.Tensor: filtered gradient
    """
    f = image_grad.new_tensor(lowpass / lowpass.mean())
    pp = torch.fft.fft2(image_grad.data)
    out = torch.fft.ifft2(pp * f)
    return out


def naive_gradient_ascent_step(
    loss_function: torch.nn.Module,
    encoding_model: torch.nn.Module,
    image: torch.Tensor,
    lowpass: torch.Tensor,
    neuron_idx: int,
    step_gain: float = 1,
    lr: float = 1.5,
    sigma: float = 0.5,
    *args: int,
    **kwargs: int,
) -> torch.Tensor:
    """Performs one step of naive gradient ascent.

    Adds the scaled gradient to the image and return it.

    Args:
        loss_function (torch.nn.Module): loss function a.k.a. loss_function.
        encoding_model (torch.nn.Module): trained encoding model which is the
            basis for the meis
        image (torch.Tensor): gaussian white noise image in pytorch convention.
        lowpass (torch.Tensor): constant tensor required for lowpass filtering of
            gradient.
        neuron_idx (int): neuron to analyize

        lr (float, optional): Learning rate. Defaults to 0.01.

    Returns:
        torch.Tensor: image after one gradient ascent step.
    """
    # Image normalization
    with torch.no_grad():
        image /= image.max()

    # Forward pass
    loss = loss_function(encoding_model(image), neuron_idx)

    # Backward pass, computes gradient: image.grad
    loss.backward()
    print(image.grad)

    # Lowpass filtering of gradient
    a = lowpass_filtering_in_frequency_domain(image.grad, lowpass)
    print(a)

    # Gradient ascent step as described by Walker et al. 2019.
    with torch.no_grad():
        image += (
            (lr / torch.abs(image.grad).mean() + 1e-12) * (step_gain / 255) * image.grad
        )
        # Image blurring with gaussian blur
        image = torchvision.transforms.functional.gaussian_blur(image, 3, sigma)
    image.grad = None
    return image


def mei(
    loss_function: torch.nn.Module,
    encoding_model: torch.nn.Module,
    image: torch.Tensor,
    selected_neuron_indicies: list,
    device: str = None,
    lr_start: float = 1,
    lr_end: float = 0.0001,
    epochs: int = 200,
    show: bool = False,
    show_last: bool = True,
    sigma_start: float = 1,
    sigma_end: float = 0.05,
    wandb_entity: str = "leeeeon4",
    *args: int,
    **kwargs: int,
) -> dict:
    """Compute the MEIs.

    Computes the MEIs by means of gradient ascent for the selected_neuron_indicies list and stores them.

    Args:
        loss_function (torch.nn.Module): Loss function
        encoding_model (torch.nn.Module): encoding model which is basis for MEIs
        image (torch.Tensor): Gaussian white noise image
        selected_neuron_indicies (list): List of neurons to compute MEIs for
        device (str, optional): If None, tries cuda. Defaults to None.
        lr_start (float, optional): Staring Learning Rate. Defaults to 1.
        lr_end (float, optional): Last Learning Rate. Defaults to 0.001.
        epochs (int, optional): Number of epochs. Defaults to 200.
        show (bool, optional): If True, MEIs are shown after every 10 steps.
            Defaults to False.
        show_last (bool, optional): If True, saves final MEI. Defaults to True
        sigma_start (float, optional): Starting simga for gaussian blurring.
            Defaults to 1
        sigma_end (float, optional): Last sigma for gaussian blurring. Defaults
            to 0.05.
        wandb_entity (str, optional): WandB entity. Defaults to 'leeeeon4'.

    Returns:
        dict: Dictionary of neuron_idx and the associated MEI.
    """

    meis = {}
    t = string_time()
    # Initialize Tensors for Low pass filtering
    lowpass = get_lowpass_tensor(image)
    lrs = torch.linspace(lr_start, lr_end, epochs).tolist()
    sigmas = torch.linspace(sigma_start, sigma_end, epochs).tolist()

    for neuron_counter, neuron in enumerate(selected_neuron_indicies):
        # Initialize wandb, config and directories
        run = wandb.init(entity=wandb_entity, project=f"invariances_mei")
        wandb_name = run.name
        wandb_config = wandb.config
        meis_directoy = Path.cwd() / "data" / "processed" / "MEIs" / f"{t}_{wandb_name}"
        meis_directoy.mkdir(parents=True, exist_ok=True)
        trainer_config = {
            "loss_function_type": loss_function.__class__.__name__,
            "encoding_model_type": encoding_model.__class__.__name__,
            "epochs": epochs,
            "neuron_idx": neuron,
            "wandb_name": wandb_name,
            "wandb_entity": wandb_entity,
            "lr_start": lr_start,
            "lr_end": lr_end,
            "sigma_start": sigma_start,
            "sigma_end": sigma_end,
        }
        wandb_config.update(trainer_config)

        # initial step
        old_image = image.detach().clone()
        old_image.requires_grad = True
        new_image = naive_gradient_ascent_step(
            loss_function=loss_function,
            encoding_model=encoding_model,
            lr=lrs[0],
            sigma=sigmas[0],
            image=old_image,
            lowpass=lowpass,
            **trainer_config,
        )
        for epoch in track(
            range(epochs - 1),
            total=epochs,
            description=f"Neuron {neuron_counter+1}/{len(selected_neuron_indicies)}: ",
        ):
            epoch += 1
            # Do gradient Ascent step
            new_image = naive_gradient_ascent_step(
                loss_function=loss_function,
                encoding_model=encoding_model,
                lr=lrs[epoch],
                sigma=sigmas[epoch],
                image=new_image,
                lowpass=lowpass,
                **trainer_config,
            )

            if show and epoch % 10 == 0:
                fig, ax = plt.subplots(figsize=(6.4 / 2, 3.6 / 2))
                im = ax.imshow(new_image.detach().numpy().squeeze())
                ax.set_title(f"Image neuron {neuron} after {epoch} epochs")
                plt.colorbar(im)
                plt.tight_layout()
                plt.show(block=False)
                plt.pause(0.1)
                plt.close()
        save(
            file=meis_directoy / f"MEI_neuron_{neuron}.npy",
            arr=new_image.detach().cpu().numpy(),
        )
        if (meis_directoy / "readme.md").exists() is False:
            with open(meis_directoy / "readme.md", "w") as f:
                f.write(
                    "# Most Exciting Images\n"
                    "The MEIs (Most Exciting Images) store the pytorch 4D representation"
                    "of the image per neuron. Dimensions are (batchsize, channels, "
                    "height, width)."
                )
        meis[neuron] = new_image
        if show:
            fig, ax = plt.subplots(figsize=(6.4 / 2, 3.6 / 2))
            im = ax.imshow(new_image.detach().cpu().numpy().squeeze())
            ax.set_title(f"Final image neuron {neuron}")
            plt.colorbar(im)
            plt.tight_layout()
            plt.show(block=False)
            plt.pause(3)
            plt.close("all")
        if show_last:
            img = new_image.detach().cpu().numpy().squeeze()
            activations = encoding_model(new_image)
            plt.imshow(img, cmap="gray")
            plt.colorbar()
            plt.title(f"Activation: {activations[:,neuron].item()}")
            image_title = f"mei_neuron_{neuron}.png"
            image_directory = Path.cwd() / "reports" / "figures" / "mei" / t
            image_directory.mkdir(parents=True, exist_ok=True)
            plt.savefig(image_directory / image_title, facecolor="white")
            plt.close()
    return meis
