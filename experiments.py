import numpy as np
from rich import print
from csng_invariances.linear_receptive_field import *
from csng_invariances.utility.data_helpers import get_test_dataset
import datetime


def main():
    ######################### Regularization factors ########################
    reg_factors = [1 * 10 ** x for x in np.linspace(0, 2, 7)]

    ############################### Lurz ###############################
    ############################### Data ###############################
    print("\n\n================================================")
    print("Begin linear receptive field estimation experiment on Lurz dataset.")
    print("================================================\n\n")

    # real data
    # (
    #     train_images,
    #     train_responses,
    #     val_images,
    #     val_responses,
    # ) = get_lurz_dataset()
    # print(
    #     f"{train_images.shape}\n{train_responses.shape}\n{val_images.shape}\n{val_responses.shape}"
    # )
    # print("-----------------------------------------------\n")

    # test data
    train_images, train_responses, val_images, val_responses = get_test_dataset()

    ####################### Global regularization ######################
    # print("\n-----------------------------------------------")
    # print("Begin globally regularized linear receptive field estimate experiments.")
    # print("-----------------------------------------------\n")

    # # Store current time
    # t = str(datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S"))

    # # Conduct hyperparameter search
    # globally_regularized_linear_receptive_field(
    #     reg_factors, train_images, train_responses, val_images, val_responses
    # )

    # Create directory and store filters
    print("\n-----------------------------------------------")
    print("Finished globally regularized linear receptive field estimate experiment.")
    print("-----------------------------------------------\n")

    ###################### Individual regularization ######################
    print("\n-----------------------------------------------")
    print("Begin indivially regularized linear receptive field estimate experiment.")
    print("-----------------------------------------------\n")

    # Conduct hyperparameter search
    individually_regularized_linear_receptive_field(
        reg_factors, train_images, train_responses, val_images, val_responses
    )

    # Store filter
    print("\n\n================================================")
    print("Lurz dataset concluded.")
    print("================================================\n\n")

    ############################## Antolik ##############################

    print("\n\n================================================")
    print("Begin Antolik dataset.")
    print("================================================\n\n")
    for region in ["region1", "region2", "region3"]:
        print("\n-----------------------------------------------")
        print(f"Being {region}.")
        print("-----------------------------------------------\n")

        ############################### Data ##############################
        # real data
        # (
        #     train_images,
        #     train_responses,
        #     val_images,
        #     val_responses,
        # ) = get_antolik_dataset(region)
        # print(
        #     f"{train_images.shape}\n{train_responses.shape}\n{val_images.shape}\n{val_responses.shape}"
        # )

        # test data
        train_images, train_responses, val_images, val_responses = get_test_dataset()

        ####################### Global regularization ######################
        print("Begin globally regularized linear receptive field estimate experiments.")
        print("-----------------------------------------------\n")

        # Conduct hyper parameter search
        globally_regularized_linear_receptive_field(
            reg_factors, train_images, train_responses, val_images, val_responses
        )

        # Store filter
        print(
            "Finished globally regularized linear receptive field estimate experiment."
        )
        print("-----------------------------------------------\n")

        ###################### Individual regularization #####################
        print(
            "Begin indivially regularized linear receptive field estimate experiment."
        )
        print("-----------------------------------------------\n")

        # Conduct hyperparametersearch
        individually_regularized_linear_receptive_field(
            reg_factors, train_images, train_responses, val_images, val_responses
        )

        # Store filter
        print("\n-----------------------------------------------")
        print(f"Conclude {region}.")

    print("\n\n================================================")
    print("Antolik dataset concluded.\n\n")
    print("================================================\n\n")


if __name__ == "__main__":
    main()
